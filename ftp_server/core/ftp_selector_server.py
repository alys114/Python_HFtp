# Author: Vincent.chan
# Blog: http://blog.alys114.com

import os
import time
import json
import selectors
import socket
import hashlib
import common
import constConfig

# 全局变量
HOST='127.0.0.1'
PORT=21567
BUFSIZ=1024
ADDR=(HOST,PORT)
CODING='utf-8'
VIR_PATH_PRE = constConfig.BASE_DIR + os.sep

class FTPSelector():
	def __init__(self):
		self.sock = socket.socket()
		self.sock.bind(ADDR)
		self.sock.listen(1000)
		self.sock.setblocking(False)  # 设置TCP为不阻塞模式
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 地址重用
		self.sel = selectors.DefaultSelector()
		self.sel.register(self.sock, selectors.EVENT_READ, self.accept)  # 注册其为先监听链接

	def accept(self, sock, mask):
		'''
		仅仅是接收链接
		:param sock:
		:param mask:
		:return:
		'''
		conn, addr = sock.accept()  # Should be ready
		print('accepted', conn, 'from', addr, 'mask>>',mask)
		conn.setblocking(False)

		self.sel.register(conn, selectors.EVENT_READ, self.interactive) # 注册其为处理客户端请求

	def interactive(self, conn, mask):
		'''
		处理请求
		:param conn:
		:param mask:
		:return:
		'''
		self.request = conn
		data = conn.recv(BUFSIZ)  # Should be ready

		if data:
			print('echoing', repr(data), 'to', conn, 'mask>>',mask)
			data = data.decode(CODING)
			data = json.loads(data)
			action = data['action']
			# print(data)
			if hasattr(self, action):
				func = getattr(self, action)
				func(data)

		else:
			print('closing', conn)
			self.sel.unregister(conn)
			conn.close()

	def auth(self, *args):
		'''
		权限验证
		:param args:
		:return:
		'''
		# 获取参数
		cmd = args[0]
		user_name = cmd['user_name']
		password = cmd['password']
		# 获取用户信息
		user_info = common.jsonLoad(constConfig.USER_DB)
		auth_result = {'user_name':user_name,'result':False,'msg':'',
					   'user_home':'',
					   'limit_size':0,
					   'used_size':0
					   }
		# print(user_info)
		if user_info.keys().__contains__(user_name):
			if user_info[user_name][0] == password:
				self.user_name = user_name
				self.user_home_dir_server = 'data'+os.sep+user_name+os.sep
				auth_result['result'] = True
				auth_result['user_home'] = self.user_home_dir_server
				auth_result['limit_size'] = self.mb_covert(user_info[user_name][1])
				auth_result['used_size'] = self.getdirsize(VIR_PATH_PRE+self.user_home_dir_server)
			else:
				auth_result['msg'] = '501-校验失败：密码错误..'
		else:
			auth_result['msg'] = '502-校验失败：不存在该用户..'

		auth_result_json = json.dumps(auth_result)
		self.request.send(auth_result_json.encode(CODING))

	def put(self, *args):
		'''
		接收上传的文件
		:return:
		'''
		cmd = args[0]
		file_name = cmd['file_name']
		file_size = cmd['file_size']
		# 返回状态码
		self.request.send('200-ok'.encode(CODING))
		server_path = VIR_PATH_PRE + file_name
		if os.path.isfile(server_path):
			f = open(server_path + '.new','wb')
		else:
			f = open(server_path, 'wb')

		receive_size = 0
		m = hashlib.md5()

		while receive_size < file_size:
			try:
				# 解决粘包问题：获取文件大小的数据，作为边界
				cur_buf_size = file_size - receive_size
				if cur_buf_size > BUFSIZ:
					cur_buf_size = BUFSIZ
				data = self.request.recv(cur_buf_size)
				receive_size += len(data)  # 注意:一定不能+cur_buf_size,要以实际收到的数据为准
				f.write(data)
				# print(receive_size,file_size)
				m.update(data)
			except BlockingIOError as e:
				# **** 坑爹的问题 ****
				# 目前的socket是不阻塞的，当客户端数据没准备好时，服务器的recv()方法会报错:
				# BlockingIOError: [WinError 10035] 无法立即完成一个非阻止性套接字操作。
				# 因此，需要捕捉这个异常，并让服务器暂时歇一下，等客户端把数据准备好。
				time.sleep(0.5)
				continue
		else:
			local_md5 = m.hexdigest()
			client_md5 = self.request.recv(BUFSIZ)
			client_md5 = client_md5.decode(CODING)
			# print('local_md5:',local_md5)
			# print('client_md5:', client_md5)
			if local_md5 == client_md5:
				print('201-file recv done.')
		f.close()

	def get(self, *args):
		'''
		下载文件
		:param args:
		:return:
		'''
		# self.request.setblocking(True)
		cmd = args[0]
		file_name = cmd['file_name']
		server_path = VIR_PATH_PRE + file_name
		if os.path.isfile(server_path):
			file_size = os.stat(server_path).st_size
			# 发送文件大小到Client

			# print(file_size)
			self.request.send(str(file_size).encode(CODING))

			while True:
				try:
					# 等待Client确认
					info_confirm = self.request.recv(BUFSIZ)
					break
				except Exception as e:
					time.sleep(0.5)
					continue

			# # 等待Client确认
			# info_confirm = self.request.recv(BUFSIZ)

			m = hashlib.md5()
			# 获取文件
			f = open(server_path, 'rb')
			for line in f:
				m.update(line)
				self.request.send(line)
			f.close()
			server_md5 = m.hexdigest()
			print('204-send done')
			self.request.send(server_md5.encode())

	def mb_covert(self,limit_size):
		size = limit_size.upper().replace('MB', '')
		size = int(size)
		size = 1024 * 1024 * size
		return size

	def getdirsize(self,dir):
		file_size = 0
		for root, dirs, files in os.walk(dir):
			# print(root, dirs, files)
			file_size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
		return file_size


def main():
	ftp_server = FTPSelector()
	while True:
		events = ftp_server.sel.select()
		for key, mask in events:
			callback = key.data
			callback(key.fileobj, mask)


if __name__ == '__main__':
	main()