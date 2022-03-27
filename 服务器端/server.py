import queue
import socket
import threading
import time  # 引入time模块
from os.path import basename

IP = socket.gethostbyname(socket.gethostname())  # 当前设备ip
PORT = 6000  # udp服务器端口
ConnectedDivice = []  # 已知的在线设备列表
state = dict()  # 设备状态
Pipe = dict()  # 各个设备对应的三级子进程进程与二级子进程的通信管道
OCCUIPED = ""  # 聊天窗口是否被占用
addro = (IP, PORT)
BUFFER_SIZE = 1024
e = threading.Event()
# 要发送的文件和接收端地址
fn_path = ''
# 存放每块数据在文件中的起点
positions = []
file_name = []
print("当前服务器IP为：" + IP)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP套接字的名字SOCK_DGRAM，特点：不可靠（局网内还是比较可靠的），开销小
s.bind((IP, PORT))
print("当前端口号为：" + str(PORT))


# 文件传输 占用端口7777
# 三级子进程（父进程：设备对应进程）
# 变量：(传输文件名称,客户端套接字)
def sendto(fn_path, addr):
    # 读取文件全部内容
    with open(fn_path, 'rb') as fp:
        content = fp.read()
    # 获取文件大小，做好分块传输的准备
    fn_size = len(content)
    for start in range(fn_size // BUFFER_SIZE + 1):
        positions.append(start * BUFFER_SIZE)
    # 设置事件，可以启动用来接收确认信息的线程了
    e.set()
    # 窗口套接字，设置发送缓冲区大小
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUFFER_SIZE)
    # 发送文件数据，直到所有分块都收到确认，否则就不停地循环发送
    while positions:
        for pos in positions:
            sock.sendto(f'{pos}_'.encode() + content[pos:pos + BUFFER_SIZE], (addr[0], 7777))
        time.sleep(0.1)
    # 通知，发送完成
    while file_name:
        sock.sendto(b'over_' + file_name[0], (addr[0], 7777))
    # 关闭套接字
    sock.close()


# 确认客户端返回的确认信息 占用端口7778
# 三级子进程（父进程：设备对应进程）
# 变量：空
def recv_ack():
    # 创建套接字，绑定本地端口，用来接收对方的确认信息
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP, 7778))
    # 如果所有分块都确认过，就结束循环
    while positions:
        # 预期收到的确认包格式为1234_ack
        data, _ = sock.recvfrom(1024)
        pos = int(data.split(b'_')[0])
        if pos in positions:
            positions.remove(pos)
    # 确认对方收到文件名，并已接收全部数据
    while file_name:
        data, _ = sock.recvfrom(1024)
        fn = data.split(b'_')[0]
        if fn in file_name:
            file_name.remove(fn)
    sock.close()


# 整合发送一条udp消息
# 变量：(消息,发送到的客户机的套接字)
def sendOne(msg, addr):
    s.sendto(msg.encode(), addr)


# 循环发送消息到客户端（聊天功能）
# 变量：(发送到的客户机的套接字)
def circlesend(addr):
    global OCCUIPED
    while OCCUIPED:
        send_data = input("To" + str(addr) + ":")
        s.sendto(send_data.encode(), addr)
        if send_data == "exitchat":
            OCCUIPED = False
            break


# 获取文件函数，用于启动发送文件进程和确认客户端返回的确认进程
# 变量：(文件路径,发送到的客户机的套接字)
def getfire(datapath, addr):
    global fn_path, file_name
    fn_path = datapath
    file_name = [f'{basename(fn_path)}'.encode()]
    t1 = threading.Thread(target=sendto, args=(fn_path, addr))
    t1.start()
    e.clear()
    e.wait()
    t2 = threading.Thread(target=recv_ack)
    t2.start()
    # 等待发送线程和接收确认线程都结束
    t2.join()
    t1.join()


# 默认命令消息处理函数
# 变量：(消息,发送到的客户机的套接字)
def mafun(message, addr):
    if message == "help":
        sendOne("\n1.返回当前服务器时间\n2.聊天\n3.文件传输\n4.关于\nexit——退出 help——帮助", addr)  # man——指令详情
    elif message == "1":
        ticks = time.time()
        sendOne("\n当前服务器时间戳为:" + str(ticks) + "\n当前服务器时间为" + str(time.asctime(time.localtime(ticks))), addr)
    elif message == "2":
        global OCCUIPED
        if OCCUIPED != "":
            return "聊天室搭建失败，聊天室被占用！"
        else:
            OCCUIPED = str(addr)
            tsend = threading.Thread(target=circlesend, args=(addr,))  # 开启发送消息线程
            tsend.start()
            sendOne("chatconfirm", addr)
    elif message == "3":
        sendOne("transferconfirm", addr)
        datapath = Pipe[addr].get()
        getfire(datapath, addr)  # 调用获取文件函数
        print("文件传输完成")
    elif message == "4":
        sendOne("\n本程序是我的计算机网络小学期作业\n@author: 朱安杰 194020215", addr)
    else:
        sendOne("未知命令：" + message, addr)


# 连接到服务器后的设备所启动线程调用的函数
# 变量(发送到的客户机的套接字)
def diviceConnect(addr):
    global OCCUIPED
    while state[addr]:
        msg = Pipe[addr].get()
        if OCCUIPED == str(addr):
            if msg == "exitchat":
                OCCUIPED = ""
                print("结束聊天")
                continue
            print(str(addr) + ":" + msg)
            continue
        mafun(msg, addr)


# 接受消息 持续监听6000端口 二级子进程（父进程：主进程（用户进程）；子进程：各个用户设备处理信息对应的进程）
# 接收到的消息分为两类：1.指令形消息2.内容形消息
# 指令形式消息：根据接受到的消息和判断已经存在的设备列表分配（删除）独立进程
# 内容形消息：根据套接字将消息发送给对应的进程（唤醒进程）
# 变量：空
def receive():
    while True:
        data, addr = s.recvfrom(BUFFER_SIZE)  # 获取消息
        print("终端： %s:%s 数据： " % addr + str(data))  # 打印获取信息
        if data == b"tryconnect":  # 对信息进行分类处理
            ConnectedDivice.append(addr)
            print("设备：" + str(addr) + " 已被发现！")
            state[addr] = True
            q = queue.Queue()  # 创建通信管道
            Pipe[addr] = q  # 管道存入字典
            tcreate = threading.Thread(target=diviceConnect, args=(addr,))  # 发现设备后创建分配进程给设备
            tcreate.start()
            # 创建完成后返回连接成功确认
            s.sendto(b"connectconfirm", addr)
            s.sendto("输入help获取选项列表".encode(), addr)
        elif data == b"exit":
            s.sendto(b"exitconfirm", addr)
            s.sendto(b"over", addr)
        elif data == b"overconfirm":
            print("设备：" + str(addr) + " 已主动离线！")
            del state[addr]  # 删除字典
            ConnectedDivice.remove(addr)  # 删除设备列表
        else:
            Pipe[addr].put(data.decode())


treceive = threading.Thread(target=receive)  # 开启接受消息线程
treceive.start()
treceive.join()
