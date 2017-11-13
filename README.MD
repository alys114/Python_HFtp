# 需求
SELECT版FTP:
- 使用SELECT或SELECTORS模块实现并发简单版FTP；
- 允许多用户并发上传下载文件；

# 实现思路
- 服务器使用selector多路复用的模块，来接收请求和处理请求；
- 保留沿用之前FTP的功能，例如：权限验证、上传文件和下载文件；


# 难点
多路复用的实现不太好理解，当服务器的socket链接设置为non-blocking时，
经常会出现异常：[WinError 10035] 无法立即完成一个非阻止性套接字操作。
目前我的处理方式是，通过捕捉这个异常后，暂停0.5秒，目的给客户端发送数据，
然后再循环监听客户端的数据。

# 执行
先运行服务器，再执行客户端。
FTP服务器默认地址是:127.0.0.1,端口：21

- FTP服务器
执行ftp_server/core/ftp_selector_server.py


# 部署环境


# 测试
（已写成多线程的模式，实现登录、上传和下载）

执行ftp_client/core/ftp_client


#运行截图
client_test.jpg
server_test.jpg