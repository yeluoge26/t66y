import requests
import threading
from bs4 import BeautifulSoup
import sys
import argparse
import os
import time
import random

# 如果需要连接socks代理
proxies = None #{"http": "socks5h://127.0.0.1:1031", "https": "socks5h://127.0.0.1:1031"}

class_list1 = ["[亞洲]", "[歐美]", "[動漫]", "[寫真]", "[原创]", "[其它]"]
main_url = "http://t66y.com/"
url1 = "http://t66y.com/thread0806.php?fid=8&search=&page="
url2 = "http://t66y.com/thread0806.php?fid=16&search=&page="
max_topic_thread = 5 # 最多同时下载多少个帖子
max_download_thread = 10 # 最多同时下载多少张图片

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"}


def get_with_proxy(url, **kwargs):
    try:
        if proxies is not None:
            return requests.get(url, proxies=proxies, headers=headers, **kwargs)
        else:
            return requests.get(url, headers=headers, **kwargs)
    except Exception as e:
        print(e)
        raise e


def get_pic_in_new_thread(pic_url, pic_save_path, pic_filename):
    print("downloading:", pic_filename, end="\n")
    try:
        r = get_with_proxy(pic_url, stream=True)
    except Exception as e:
        print("download img failed:", pic_filename, e, end="\n")
        return
    if r.status_code == 200:
        open(pic_save_path, 'wb').write(r.content)
        print("saved:", pic_filename, end="\n")
    else:
        print(r.status_code, ":download img failed!", pic_filename, end="\n")


def get_photo_list(url, name, **kwargs):
    retry_cnt = 0
    if kwargs is not None and "retry_cnt" in kwargs.keys():
        retry_cnt = kwargs.get("retry_cnt")
        if retry_cnt >= 2:
            # 若已经重试了一次或以上
            print("get_photo_list 超过重试限制", name[4:], end="\n")
            return []

    try:
        f = get_with_proxy(url)
    except Exception as e:
        print("get photo list failed:" + name[4:], e)
        return
    try:
        soup = BeautifulSoup(f.content, "lxml")
        if "正在轉入主題, 请稍后" in soup.text:
            # 触发了爬虫限制, 等待三秒后重新请求
            time.sleep(3)
            return get_photo_list(url, name, retry_cnt=retry_cnt + 1)
        if "頁面暫時無法載入，請您稍後重試" in soup.text:
            time.sleep(10)
            return get_photo_list(url, name, retry_cnt=retry_cnt + 1)
        photo_div = soup.find_all('div', class_="tpc_content do_not_catch")
        photo_list = photo_div[0].find_all('img')
        return photo_list
    except Exception as e:
        # 解析页面的时候可能的其他出错
        print(e)
        return []


def download_pic(name, url, path):  # 该函数用于下载具体帖子内的图片
    # count = 0  todo 多线程共享计数器
    dst_path = path + "/" + name[:4] + "/" + name[4:]
    if not os.path.exists(dst_path):
        os.makedirs(dst_path)

    photo_list = get_photo_list(url, name)
    photo_num = len(photo_list)

    thread_list = []
    for li in photo_list:
        # print(str(li))
        pic_url = str(li).split('"')[-4]
        pic_filename = pic_url.split("/")[-1]
        pic_save_path = os.path.join(dst_path, pic_filename)
        if os.path.exists(pic_save_path):
            # 若该文件已经下载过则跳过
            continue
        while get_thread_count("downloadThread") > max_download_thread:
            time.sleep(1)
        download_thread = threading.Thread(target=get_pic_in_new_thread, args=(pic_url, pic_save_path, pic_filename,))
        download_thread.setName("downloadThread" + str(random.randint(0, 1000000)))
        download_thread.start()
        time.sleep(1)
        thread_list.append(download_thread)

    for t in thread_list:
        # 每个下载线程最多等待10秒， 之后本线程会不再等待
        t.join(10)
    print(str(photo_num), " jobs done! topic: ", name[4:], end="\n")


def get_list(class_name, url):  # 该函数获取板块内的帖子列表
    '''get_list(class_name,url)'''
    if os.path.exists("./t66y/" + class_name):
        print("path['./t66y/" + class_name + "'] exists")
    else:
        os.mkdir("./t66y/" + class_name)
    post_class = ""
    try:
        f = get_with_proxy(url)
    except Exception as e:
        print("Connect failed:", e)
        sys.exit(0)

    soup = BeautifulSoup(f.content, "lxml")
    td = soup.find_all('td', class_="tal")
    post_list = dict()
    for i in td:
        if "↑" in str(i):  # 过滤几个置顶公告帖
            continue
        for item in class_list1:
            if item in str(i):
                post_class = item
                break
            else:
                post_class = "[其它]"
        post_title = i.find_all('h3')[0].find_all('a')[0].string
        post_title = post_class + post_title
        post_url = str(i.find_all('h3')[0]).split('"')[1]
        post_url = main_url + post_url
        post_list[post_title] = post_url
    print(class_name, " 该板块帖子数：", str(len(post_list)), end="\n")
    count = 0
    for key in post_list:
        # download_pic(key,post_list[key],"./t66y/"+class_name)
        while (1):
            if get_thread_count("topicThread") < max_topic_thread:
                break
            else:
                time.sleep(0.1)
        download_thread = threading.Thread(target=download_pic,
                                           args=(key, post_list[key], "./t66y/" + class_name,))  # 多线程下载
        download_thread.setDaemon(True)  # 设置守护进程, 主线程退出时， OS自动结束所有下载线程
        download_thread.setName("topicThread" + str(random.randint(0, 1000000)))
        download_thread.start()
        count += 1
        print(class_name, "该板块进度： (", str(count), "/", str(len(post_list)), ")", end="\n")


# 根据前缀获取正在运行的线程数
def get_thread_count(thread_prefix):
    count = 0
    for t in threading.enumerate():
        if t.getName().startswith(thread_prefix):
            count += 1
    return count


def pre_exit():
    while (1):
        thread_unfinished = threading.active_count() - 1
        if thread_unfinished > 0:
            print("\n***剩余下载线程：[", thread_unfinished, "]***")
            print("若长时间响应请手动结束进程...")
            time.sleep(8)
        else:
            print("下载已完成！")
            sys.exit(0)


def main():
    # global proxies
    global max_topic_thread
    global max_download_thread
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--class_id', type=int, default=0,
                        help="'1' for 【新時代的我們】, '2' for 【達蓋爾的旗幟】, '0' for both")
    parser.add_argument('-s', '--start', type=int, default=1, help="Page_start(default=1)")
    parser.add_argument('-e', '--end', type=int, default=100, help="Page_end")
    parser.add_argument('-mt', '--max_topic_thread', type=int, default=5, help="Max topic thread num(default=5)")
    parser.add_argument('-md', '--max_download_thread', type=int, default=10, help="Max download thread num(default=10)")
    args = parser.parse_args()
    class_id = args.class_id
    start = args.start
    end = args.end
    max_topic_thread = args.max_topic_thread
    max_download_thread = args.max_download_thread

    if class_id > 2:
        print("Sorry no class [", class_id, "] !")
        sys.exit(0)
    if end < start or start < 1:
        print("Bad range!")
        sys.exit(0)
    if os.path.exists("./t66y"):
        print("path[',/t66y'] exists")
    else:
        os.mkdir("./t66y")
    print("Enjoy your life!")
    if class_id == 0:
        print("将下载【新時代的我們】和【達蓋爾的旗幟】的图片...")
        for i in range(start, end + 1):
            print("开始下载第", i, "页")
            get_list("新時代的我們", url1 + str(i))
            get_list("達蓋爾的旗幟", url2 + str(i))
        pre_exit()
    else:
        if class_id == 1:
            print("将下载【新時代的我們】的图片...")
            for i in range(start, end + 1):
                print("开始下载第", i, "页")
                get_list("新時代的我們", url1 + str(i))
            pre_exit()
        if class_id == 2:
            print("将下载【達蓋爾的旗幟】的图片...")
            for i in range(start, end + 1):
                print("开始下载第", i, "页")
                get_list("達蓋爾的旗幟", url2 + str(i))
            pre_exit()


if __name__ == "__main__":
    print("合理欣赏怡情，过度手冲伤身！")
    main()
