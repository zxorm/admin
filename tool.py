import random,inspect,types,requests

import time,pickle,traceback,threading,smtplib,urllib,logging,_thread,socket,sys,os,gzip,hashlib,random
from datetime import datetime,timedelta,date
from logging import getLogger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from concurrent import futures
def getRandomCode(length=6):
    code = []
    for i in range(length):
        code.append(str(random.randint(0, 9)))
    return ''.join(code)


#基础方法
def checkEmptys(* args):
    for i in args:
        if i is None or i =="":return True
    return False

def minfo(* args,** kwargs):
    a,b,c=1,2,3
    print(args)
    print(kwargs)

def getAllVars(l):
    m={}
    for k,v in l.items():
        if (not k.startswith("_")) and (type(v) !=types.FunctionType) and (type(v) !=types.ModuleType) :
            m[k]=v
    return m


executor = futures.ThreadPoolExecutor(max_workers=10)
log = getLogger(__name__)
__cache = None
defaultCacheExp = '300d'
__cacheChanagerKey = '__cache__is__changer'
__taskThread = None
__taskList = []
# 设置服务器，用户名、口令以及邮箱的后缀
_mail_host = "smtp.126.com"
_mail_user = "livehl"
_mail_pass = "!A2s#D4f"
_mail_postfix = "126.com"
_default_mail_to_list = ["livehl@126.com"]

CACHE_CHANGE = False
task_list_change_lock = _thread.allocate_lock()


class threadPool:
    tasks = []
    c = _thread.allocate_lock()
    d = _thread.allocate_lock()
    realThreadCount = 0

    def __init__(self, threadCount, startFun=None, endFun=None):
        self.threadCount = threadCount
        self.startFun = startFun
        self.endFun = endFun

    def addTask(self, target, *args):
        task = {'target': target, 'args': args}
        self.c.acquire()
        self.tasks.append(task)
        self.c.release()
        self.startThread()

    def run(self):
        task = self.getTask()
        if self.startFun:
            start = self.startFun()
        else:
            start = None
        while task != None:
            try:
                if start:
                    task['target'](start, *task['args'])
                else:
                    task['target'](*task['args'])
            except Exception:
                log.info(traceback.format_exc())
            task = self.getTask()
        self.realThreadCount -= 1
        if self.endFun:
            if start:
                self.endFun(start)
            else:
                self.endFun()

    def getTask(self):
        if len(self.tasks) == 0: return None
        self.c.acquire()
        task = self.tasks.pop()
        self.c.release()
        return task

    def startThread(self):
        if self.realThreadCount < self.threadCount:
            self.realThreadCount += 1
            threading.Thread(target=self.run, daemon=True).start()

    def wait(self):
        waitExit = False
        while len(self.tasks) > 0 or self.realThreadCount > 0:
            if len(self.tasks) == 0 or self.realThreadCount == 0: waitExit = 1
            if waitExit:
                waitExit += 1
                if waitExit > 30 * 10: break
            time.sleep(0.1)


def md5(str):
    return hashlib.md5(str.encode(encoding='utf-8')).hexdigest()


def now():
    return datetime.now()


def timestamp():
    # 当前时间戳
    return int(time.time() * 1000)


def getAfterDate(exp, date=None):
    # get date from date exp like 3d(ays) 2h(ours) 12m(inutes) 45s(econds)
    if not date: date = datetime.now()
    type = exp[len(exp) - 1:len(exp)]
    n = int(exp[0:len(exp) - 1])
    if type == 's':
        date += timedelta(seconds=n)
    elif type == 'm':
        date += timedelta(minutes=n)
    elif type == 'h':
        date += timedelta(hours=n)
    elif type == 'd':
        date += timedelta(days=n)
    else:
        raise Exception('unsupport type:' + type)
    return date


def getDateStr(date=time.localtime(), fmt='%Y-%m-%d %H:%M:%S'):
    return time.strftime(fmt, date)


def __getCache():
    global __cache
    # get cache
    if None == __cache:
        try:
            # 载入数据
            log.info('loading cache data')
            with open('tool.cache.pickle', 'rb') as f:
                __cache = pickle.load(f)
                log.info('load cache ok size:' + str(len(__cache)))
        except Exception:
            __cache = {}
            #            exstr = traceback.format_exc()
            log.info('load cache fail:' + str(sys.exc_info()))
        # add save cache backgroup thread
        addTask(saveCache, second=5, loop=True)
        CACHE_CHANGE = True
    __cache[__cacheChanagerKey] = True
    return __cache


def saveCache():
    if not CACHE_CHANGE: return
    if not __cache: return
    with open('tool.cache.pickle', 'wb') as f:
        pickle.dump(__cache, f)


def getCache(key, default_key=None, delayExp=False):
    # get cache
    c = __getCache()
    value = c.get(key)
    if None != value:
        if value['date'] > datetime.now():
            if delayExp:
                c[key]['date'] = getAfterDate(delayExp)
                global CACHE_CHANGE
                CACHE_CHANGE = True
            return value['data']
        else:
            del c[key]
    return default_key


def putCache(key, data=True, exp=defaultCacheExp):
    # add a cache with date exp like 3d(ays) 2h(ours) 12m(inutes) 45s(econds)
    __getCache()[key] = {'date': getAfterDate(exp), 'data': data}
    global CACHE_CHANGE
    CACHE_CHANGE = True
    return data


def addTask(target, args=None, second=None, loop=False):
    # 异步任务
    global __taskList, __taskThread
    if not __taskThread:
        __taskThread = threading.Thread(target=__taskRun, daemon=True)
        __taskThread.start()
    task_list_change_lock.acquire()
    __taskList.append({'target': target, 'args': args, 'second': second, 'loop': loop, 'default_second': second})
    task_list_change_lock.release()


def __taskRun():
    newsecond = True
    count = 100
    global __taskList
    while True:
        for t in __taskList:
            newsecond = count == 0
            if t['second']:
                if newsecond: t['second'] = t['second'] - 1
            else:
                if t['args']:
                    mailError(t['target'])(t['args'])
                else:
                    mailError(t['target'])
                if not t['loop']:
                    task_list_change_lock.acquire()
                    __taskList.remove(t)
                    task_list_change_lock.release()
                else:
                    t['second'] = t['default_second']
        if newsecond: newsecond = False;count = 100
        count -= 1
        time.sleep(0.01)


def getOpener(cj, url, data=None, head=None, timeout=30, encoder='utf-8'):
    # 带重试的url请求
    cookie_support = urllib.request.HTTPCookieProcessor(cj)
    opener = urllib.request.build_opener(cookie_support)
    if None != data:
        data = urllib.parse.urlencode(data, encoding=encoder)
        data = data.encode()
    if None != head:
        hasUA = False
        for x in head:
            if (x[0].lower() == 'User-agent'.lower()):
                hasUA = True
                break
        if not hasUA:
            head.append(('User-agent',
                         'Mozilla/5.0 (iPad; U; CPU OS 3_2_1 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Mobile/7B405'))
    else:
        head = [('User-agent',
                 'Mozilla/5.0 (iPad; U; CPU OS 3_2_1 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Mobile/7B405')]
    opener.addheaders = head
    retrycount = 5
    while retrycount > 0:
        try:
            return opener.open(url, data, timeout=timeout)
        except socket.timeout as ex:
            time.sleep(0.1)
            log.debug(traceback.format_exc())
            retrycount -= 1
            if retrycount == 0:
                raise ex


def getResuletOpener(cj, url, data=None, head=None, timeout=30, encoder='utf-8'):
    # 带重试的url请求,返回utf-8解码
    h = getOpener(cj, url, data, head, timeout, encoder)
    if h:
        encoding = h.headers['Content-Type']
        if encoding: encoding = get_txt_context(encoding, '=')
        isGzip = 'gzip' == h.headers['Content-Encoding']
        retrycount = 5
        while retrycount > 0:
            try:
                h = h.read()
                retrycount = 0
            except socket.timeout as ex:
                log.debug(traceback.format_exc())
                retrycount -= 1
                if retrycount == 0:
                    raise ex
                h = getOpener(cj, url, data, head, timeout, encoder)
        if isGzip: h = gzip.decompress(h)
        try:
            if h: h = h.decode(encoding, 'ignore')
        except Exception:
            try:
                h = h.decode('utf-8', 'ignore')
            except Exception:
                log.debug('decode utf-8 fail')
    if h: return str(h)
    return None


def retry(fun, count=3):
    # 重试
    def _retry(*args, **kwargs):
        retrycount = count
        while retrycount > 0:
            try:
                fun(*args, **kwargs)
                retrycount = 0
            except Exception as ex:
                log.debug(traceback.format_exc())
                retrycount -= 1
                if retrycount == 0:
                    raise ex

    return _retry


def loopRun(sleepTime=1):
    # 循环执行
    def _loopRun(fun):
        def _loopRun(*args, **kwargs):
            while (True):
                fun(*args, **kwargs)
                time.sleep(sleepTime)

        return _loopRun

    return _loopRun


def sendErroMail(msg=''):
    exstr = msg + '\r\n' + traceback.format_exc()
    if hasExp(exstr):
        sendMail(__name__ + '异常-------' + socket.gethostname(), exstr)
    log.warn(exstr)


def hasExp(text, time='6h'):
    if not getCache(text):
        putCache(text, True, time)
        return True
    return False


def mailError(fun):
    # 捕捉异常并发送邮件
    def _mailError(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception:
            sendErroMail()

    return _mailError


def catchErrorRun(fun, *args, **kwargs):
    try:
        return fun(*args, **kwargs)
    except Exception:
        sendErroMail()


def catchErrorRunNoMail(fun, *args, **kwargs):
    try:
        return fun(*args, **kwargs)
    except BaseException:
        pass
    except KeyError:
        pass
    else:
        pass


def cache(func, safe=False, cacheTime='30s'):
    # 缓存对象 safe为出错是否抛出异常
    def _cache(*args, **kwargs):
        key = func.__name__
        for arg in args:
            key += str(arg)
        for k in kwargs:
            key += str(k) + "_" + kwargs[k]
        if getCache(key): print("user cache");return getCache(key)
        v = None
        if safe:
            v = catchErrorRunNoMail(func, *args, **kwargs)
        else:
            v = func(*args, **kwargs)
        if v: putCache(key, v, cacheTime)
        return v

    return _cache


def sendMail(sub, content, to_list=_default_mail_to_list):
    '''
    to_list:发给谁
    sub:主题
    content:内容
    send_mail("aaa@126.com","sub","content")
    '''
    #####################
    msg = MIMEText(content)
    msg['Subject'] = sub
    return sendMailMessage(msg, to_list)


def sendMailMessage(message, to_list=_default_mail_to_list):
    '''
    发送消息
    消息体自行构造
    '''
    try:
        me = _mail_user + "<" + _mail_user + "@" + _mail_postfix + ">"
        s = smtplib.SMTP()
        s.connect(_mail_host)
        s.login(_mail_user, _mail_pass)
        s.sendmail(me, to_list, str(message))
        s.close()
        return True
    except Exception:
        return False


def getHtmlMailMessage(sub, html, images=None):
    # 以html和图片附件构建消息体
    if not images:
        msg = MIMEText(html, 'html')
        msg['Subject'] = sub
    else:
        msg = MIMEMultipart('related')
        msg['Subject'] = sub
        msg.attach(MIMEText(html, 'html'))
        for k in images:
            try:
                fp = open(images[k], 'rb')
                msgImage = MIMEImage(fp.read())
                fp.close()
                msgImage.add_header('Content-ID', k)
                msg.attach(msgImage)
            except Exception:
                sendErroMail()
    return msg


def restart():
    # 重启程序
    getCache('a')
    saveCache()
    python = sys.executable
    os.execl(python, python, *sys.argv)
    exit(0)


def reload(watchPath=os.getenv('pythonpath')):
    # 监视目录并重启
    def print_file_change_restart(f):
        print('py file change reload')
        print(f)
        restart()

    def filter(f):
        return f.endswith('.py') or not os.path.isfile(f)

    wath_file(print_file_change_restart, watchPath, filter)


def back_reload(watchPath=os.getenv('pythonpath')):
    # 后台监控文件变化
    threading.Thread(target=reload, daemon=True).start()


def wath_file(callback, watchPath=os.getenv('pythonpath'), fileter=None):
    if not watchPath: watchPath = os.getcwd()
    if watchPath.find(';') != -1: watchPath = watchPath.split(';')[0]

    # 监视文件变化
    def get_all_file_info(f, cut):
        # 列出子目录
        info = {}
        for sub_f in os.listdir(f):
            sub_f = f + '/' + sub_f
            if cut:
                if not cut(sub_f): continue
            if not os.path.isfile(sub_f):
                info.update(get_all_file_info(sub_f, cut))
            else:
                info[sub_f] = os.path.getsize(sub_f)
        return info

    before = get_all_file_info(watchPath, fileter)
    while True:
        time.sleep(3)
        after = get_all_file_info(watchPath, fileter)
        added = [f for f in after if not f in before]
        removed = [f for f in before if not f in after]
        change = [f for f in after if f in before and after[f] != before[f]]
        if added: change += added
        if removed: change += removed
        if change: callback(change)
        before = after


def sendHtmlMail(sub, html, images=None, to_list=_default_mail_to_list):
    sendMailMessage(getHtmlMailMessage(sub, html, images), to_list)


def get_txt_context(context, start, end=None):
    first = context.find(start)
    if first != -1:
        context = context[first + len(start):]
        if end:
            last = context.find(end)
            context = context[:last]
    return context


def get_text_next_context(context, start, next, end):
    first = context.find(start)
    if first != -1:
        context = context[first + len(start):]
        first = context.find(next)
        if first != -1:
            context = context[first + len(next):]
            if end:
                last = context.find(end)
                context = context[:last]
    return context


def float_dis(num, dis):
    z, x = str(num).split('.')
    return float(z + '.' + x[:dis])


def getTimeDiff(strTime, diff):
    h, m = map(lambda x: int(x), strTime.split('.'))
    m = +5
    if m >= 60:
        h += 1
        m -= 60
    if h > 24: h -= 24
    down_time = str(h) + '.' + str(m)
    m -= 10
    if m < 0:
        h -= 1
        m += 60
    if h < 0: h += 24
    return str(h) + '.' + str(m) + "-" + down_time


@retry
def re():
    print('a')
    raise Exception('a')


if __name__ == '__main__':
    #    print(datetime.now())
    #    print(getAfterDate(exp='3d'))
    #    sendMail('你妹','你妹的内容')
    #    msg=getHtmlMailMessage('html内容','<html><h1>你好</h1><img src="cid:a"></html>',{'a':'t:\\ee.jpg'})
    #    sendMailMessage(msg)
    #    re()
    #    print(getDateStr(time.localtime(int("1385423539"))))
    #    reload()
    #    print(float_dis(0.33333,2))

    pass


def startLog(level='DEBUG'):
    logging.basicConfig(level=level)
    l = getLogger()
    # 再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()
    ch.setLevel(level)
    # 定义handler的输出格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
    ch.setFormatter(formatter)
    l.addHandler(ch)
    return l

# if __name__ == '__main__':
#     # print(bool("False"))
#     # a,b,c=(1,2,3)
#     # print(locals())
#     # # minfo(a,b,c,name="123")
#     # a={"name":1}
#     # a.pop("b","")
#     # print(a)
#     page = requests.put('http://127.0.0.1/api/admin/generateRole')
#     print(page.text)
#     # print(getAllVars(locals()))