import os
import queue
import socket
import threading

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
Connect = False
progress = []
IP = input("服务器ip：")
PORT = 6000
addr = (IP, PORT)

go = False
print("--------连接服务器--------")
while True:
    s.sendto("tryconnect".encode(), addr)
    dataresponse, addred0 = s.recvfrom(1024 * 1024)
    if dataresponse == b"connectconfirm" and addred0[0] == IP:
        print("--------连 接 成 功--------")
        break
    else:
        print("连接失败，尝试重新连接中")


# 获取文件路径，名称
# 变量(文件名)
def getFile(filename):
    filepath, tempfilename = os.path.split(filename)
    shotname, extension = os.path.splitext(tempfilename)
    return filepath, shotname, extension


# 接受消息 持续监听端口 二级子进程（父进程：主进程（用户进程））
def receive():
    global go
    while True:
        if go:
            break
        response, addred = s.recvfrom(1024 * 1024)
        if response == b"exitconfirm":
            responsee, addrede = s.recvfrom(1024 * 1024)
            if responsee == b"over":
                s.sendto("overconfirm".encode(), addr)
                print("--------断开服务器：%s:%s--------" % addr)
                s.close()
                go = True
                break
        elif response == b"chatconfirm":
            continue
        elif response == b"transferconfirm":
            print("--------文 件 传 输--------")
            getfirename = input('请输入想要获取的文件:')
            dst = input('请输入用来保存文件的目标位置:')
            s.sendto(getfirename.encode(), addr)
            BUFFER_SIZE = 1024 * 1024
            # 用来临时保存数据
            data = set()
            # 接收数据的Socket
            sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_recv.bind((IP, 7777))
            # 确认反馈地址
            ack_address = (IP, 7778)
            sock_ack = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 重复收包次数
            repeat = 1
            while True:
                buffer, _ = sock_recv.recvfrom(BUFFER_SIZE)
                # 全部接收完成,获取文件名
                if buffer.startswith(b'over_'):
                    fn = buffer[5:].decode()
                    # 多确认几次文件传输结束,防止发送方丢包收不到确认
                    for i in range(5):
                        sock_ack.sendto(fn.encode() + b'_ack', ack_address)
                    break
                # 接收带编号的文件数据,临时保存,发送确认信息
                buffer = tuple(buffer.split(b'_', maxsplit=1))
                if buffer in data:
                    repeat = repeat + 1
                else:
                    data.add(buffer)
                sock_ack.sendto(buffer[0] + b'_ack', ack_address)
            sock_recv.close()
            sock_ack.close()
            print(f'重复接收数据{repeat}次')
            data = sorted(data, key=lambda item: int(item[0]))
            with open(rf'{dst}/{fn}', 'wb') as fp:
                for item in data:
                    fp.write(item[1])
            print("传输完成")
            q.put(1)

        else:
            print("%s:%s：" % addr + str(response.decode()))


# 发送消息
def circlesend():
    while True:
        send_data = input()
        s.sendto(send_data.encode(), addr)
        if send_data == "3":
            q.get()
        if go:
            break


q = queue.Queue()
treceive = threading.Thread(target=receive)  # 开启接受消息线程
treceive.start()
tsend = threading.Thread(target=circlesend)  # 开启发送消息线程
progress.append(tsend)
tsend.start()
treceive.join()
tsend.join()
