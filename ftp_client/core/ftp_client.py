# Author: Vincent.chan
# Blog: http://blog.alys114.com

import os
import time
import hashlib
import getpass
import json
import threading
from socket import *
import common


HOST = '127.0.0.1'
PORT = 21567
ADDR = (HOST,PORT)
BUFSIZ = 8192
CODING = 'utf-8'


class FtpClient(object):
	def __init__(self):
		self.client = socket()


	def connect(self,addr):
		self.client.connect(addr)
		print('connected server'.center(50,'-'))

	def interactive(self,p_user,p_pwd,cmd):
		'''
		命令响应程序
		:return:
		'''
		# while True:
		self.auth = self.authorization(p_user,p_pwd)
		if self.auth:
			# cmd = input('[%s %s] #'%(self.user_name,self.user_cur_dir))
			# cmd = input('>>>')
			# print(cmd)
			# if cmd is None:
			# 	break
			if len(cmd.strip())>0:
				cmd_str = cmd.split()[0]
				# 利用反射
				if hasattr(self, 'cmd_' + cmd_str):
					func = getattr(self, 'cmd_' + cmd_str)
					func(cmd)
				else:
					self.help_action()
				# print(self.auth)

	def cmd_put(self,*args):
		'''
		上传文件
		:return:
		'''
		cmd_split = args[0].split()
		if len(cmd_split)>1:
			file_name = cmd_split[1]
			if os.path.isfile(file_name):
				# 组织头文件，发送给客户端确认
				file_size = os.stat(file_name).st_size
				if self.user_cur_dir[-1] ==os.sep:
					client_path = self.user_cur_dir + file_name
				else:
					client_path = self.user_cur_dir + os.sep + file_name

				# 额度校验
				if self.limit_size < self.used_size + file_size:
					common.errorPrompt('已超过上传的额度[%s]k，当前已用[%s]k,当前文件[%s]k'
									   %(self.limit_size,self.used_size,file_size))
					return
				header={
					'file_name':client_path,
					'file_size':file_size,
					'overridden':True,
					'action':'put'
				}
				header_json = json.dumps(header)
				self.client.send(header_json.encode(CODING))

				client_reply = self.client.recv(BUFSIZ).decode()
				# 回复码验证
				if client_reply.__contains__('200'):
					print('上传开始....')
					m = hashlib.md5()
					f = open(file_name,'rb')
					send_size = 0
					for line in f:
						self.client.send(line)
						m.update(line)
						send_size += len(line)
						percent = send_size / file_size  # 接收的比例
						common.progress(percent, width=80)  # 进度条的宽度80
					f.close()
					local_md5 = m.hexdigest()
					self.client.send(local_md5.encode(CODING))
					print('send done')

			else:
				print(file_name,' is not exit')

	def cmd_get(self,*args):
		'''
		下载文件()
		:return:
		'''
		cmd_split = args[0].split()
		if len(cmd_split) > 1:
			file_name = cmd_split[1]
			if self.user_cur_dir[-1] == os.sep:
				client_path = self.user_cur_dir + file_name
			else:
				client_path = self.user_cur_dir + os.sep + file_name
			header = {
				'file_name': client_path,
				'action': 'get'
			}
			header_json = json.dumps(header)
			self.client.send(header_json.encode(CODING))
			# 获取文件信息
			server_reply = self.client.recv(BUFSIZ).decode(CODING)
			# print(server_reply)
			# 客户端确认
			self.client.send('ok'.encode(CODING))
			file_size = int(server_reply)
			receive_size = 0
			file_name = cmd_split[1]
			m = hashlib.md5()

			print('下载开始....')

			# 写本地文件
			with open(file_name + '.new', 'wb') as f:
				while receive_size < file_size:
					# 解决粘包问题：获取文件大小的数据，作为边界
					cur_buf_size = file_size - receive_size
					if cur_buf_size > BUFSIZ:
						cur_buf_size = BUFSIZ

					data = self.client.recv(cur_buf_size)
					f.write(data)
					receive_size += len(data)  # 注意:一定不能+cur_buf_size,要以实际收到的数据为准
					m.update(data)
					percent = receive_size / file_size  # 接收的比例
					common.progress(percent, width=80)  # 进度条的宽度80
				else:
					local_md5 = m.hexdigest()
					server_md5 = self.client.recv(BUFSIZ)
					server_md5 = server_md5.decode()
					if local_md5 == server_md5:
						print('file rec done.')
					else:
						common.errorPrompt('data is missing or changed..')

	def authorization(self,p_user,p_pwd):
		'''
		权限验证
		:return:True --> Pass
		'''
		# user_name = input('username:')
		# # password = getpass.getpass('password:') #在pycharm中不起作用
		# password = input('password:')

		user_name = p_user
		password = p_pwd
		# md5加密
		password = common.md5Encode(password)
		data = {
			'user_name':user_name,
			'password':password,
			'action':'auth'
				}
		auth_info = json.dumps(data)
		self.client.send(auth_info.encode(CODING))
		server_reply = self.client.recv(BUFSIZ)
		auth_result = json.loads(server_reply.decode(CODING))
		# print('user_name:',auth_result)
		if auth_result['result']:
			self.user_name = user_name
			self.user_def_dir = auth_result['user_home']
			self.user_cur_dir = auth_result['user_home']
			self.user_old_dir = auth_result['user_home']
			self.limit_size = auth_result['limit_size']
			self.used_size = auth_result['used_size']
			return True

		else:
			common.errorPrompt(auth_result['msg'])
			return False

	def cmd_quit(self,*args):
		self.auth = False

	def help_action(self):
		'''
		使用帮助
		:return:
		'''
		msg = '''
-------------------
下载文件：get filename
上传文件：put filename
-------------------
		'''
		print(msg)


def main(p_user,p_pwd,cmd):
	ftp_client = FtpClient()
	ftp_client.client.connect(ADDR)
	ftp_client.interactive(p_user,p_pwd,cmd)
	ftp_client.client.close()


if __name__ == '__main__':
	# 上传文件
	thread1 = threading.Thread(target=main,args=('user1','123456','put 2.jpg',))
	thread1.start()
	thread2 = threading.Thread(target=main, args=('user2', '123456','put 1.txt',))
	thread2.start()

	# 等待上传成功后，再调用下载的线程
	time.sleep(3)

	# 下载文件
	thread3 = threading.Thread(target=main, args=('user1', '123456', 'get 2.jpg',))
	thread3.start()
	thread4 = threading.Thread(target=main, args=('user2', '123456', 'get 1.txt',))
	thread4.start()

