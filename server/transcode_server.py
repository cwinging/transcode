#!/usr/bin/python
# encoding:utf-8

import urllib2
import urllib
import json
from converter import Converter
from converter import ConverterError,FFMpegConvertError,FFMpegError
import multiprocessing
import logging
import os
import os.path
import time
import md5
import multiprocessing
import ConfigParser
import argparse
import base64
import re
from daemon import Daemon
from multiprocessing_logging import install_mp_handler
import logging.handlers
import uuid

logger = logging.getLogger(__name__)
task_logger = logging.getLogger('transcode_task')

default_nginx_addr = 'http://192.168.1.119'
default_root = '/mfs/web'
default_log = '/home/swift/transcode/logs/transcode.log'
default_tasklog = '/home/swift/transcode/logs/transcode_task.log'
default_pidfile = '/home/swift/transcode/logs/transcode.pid'
httpmq_url = "http://172.16.99.224:9000/?charset=utf-8&name=transcodequeue&opt=get&auth=abc"
connect_timeout_in_second = 10

def urlsafe_base64_encode(string):
    """
    Removes any `=` used as padding from the encoded string.
    """
    encoded = base64.urlsafe_b64encode(string)
    return encoded.rstrip("=")

def urlsafe_base64_decode(string):
    """
    Adds back in the required padding before decoding.
    """
    padding = 4 - (len(string) % 4)
    string = string + ("=" * padding)
    #print 'encode url safe string=%s, type=%s' % (string, type(string))
    if type(string) == unicode:
        string = string.encode()

    return base64.urlsafe_b64decode(string)

def read_config(filename):
    """
    read transcode system config
    """
    config = ConfigParser.ConfigParser()
    config.read(filename)
    
    try:
        my_httpmq = config.get('sysconfig', 'httpmq')
    except ConfigParser.Error, e:
        my_httpmq = None

    try:
        log = config.get('sysconfig', 'log')
    except ConfigParser.Error, e:
        log = None

    try:
        log_level = config.get('sysconfig', 'log_level')
    except ConfigParser.Error, e:
        log_level = None

    try:
        notify_url = config.get('sysconfig', 'notify_url')
    except ConfigParser.Error, e:
        notify_url = None

    try:
        task_log = config.get('sysconfig', 'task_log')
    except ConfigParser.Error, e:
        task_log = None
        
    try:
        pidfile = config.get('sysconfig', 'pidfile')
    except ConfigParser.Error, e:
        pidfile = None

    try:
        progress_url = config.get('sysconfig', 'progress_url')
    except ConfigParser.Error, e:
        progress_url = None

    return my_httpmq, log, log_level, task_log, pidfile, notify_url, progress_url

def get_log_level(log_level):
    log_level_table = {'ALL':logging.NOTSET, 'DEBUG':logging.DEBUG, 'INFO':logging.INFO, 'WARNING':logging.WARNING, 'ERROR':logging.ERROR, 
    'CRITICAL':logging.CRITICAL}

    level = log_level_table.get(log_level, logging.WARNING)
    return level

def init_logger(logger, level=logging.WARNING, logfile='transcode.log'):
    logger.setLevel(level)
    #f = logging.FileHandler(filename=logfile, mode='a')
    f = logging.handlers.TimedRotatingFileHandler(filename=logfile, when='M', interval=5, backupCount=5)
    f.setLevel(level)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    f.setFormatter(formatter)
    
    # add multiprocess hander
    #logger.addHandler(f)
    install_mp_handler(logger, f)



def get_cpu_count():
    try:
        cpus = multiprocessing.cpu_count()
    except NotImplementedError, e:
        cpus = 4
    return cpus

def parse_persistent_ops(cmd):
    """
    convert persistentOps to dict
    """
    cmd_argv = cmd.split('/')
    files = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 == 0]
    values = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 != 0]
    request = dict(zip(files, values))
    return request

def get_watermark_ops(request, rootdir):
    """
    get watermark filters from request
    """
    wm_image = request.get('wmImage', None)
    wm_text = request.get('wmText', None)

    watermark_filters = []

    if wm_image:
        wm_gravity = request.get('wmGravity', 'NorthEast')
        wm_offsetx = request.get('wmOffsetX', 0)
        wm_offsety = request.get('wmOffsetY', 0)
        
        overlay_gravity_table = {'NorthWest':'x=0:y=0',
            'North':'x=(main_w-overlay_w)/2:y=0',
            'NorthEast':'x=main_w-overlay_w:y=0',
            'West':'x=0:y=(main_h-overlay_h)/2',
            'Center':'x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2',
            'East':'x=main_w-overlay_w:y=(main_h-overlay_h)/2',
            'SouthWest':'x=0:y=main_h-overlay_h',
            'South':'x=(main_w-overlay_w)/2:y=main_h-overlay_h',
            'SouthEast':'x=main_w-overlay_w:y=main_h-overlay_h',
        }

        image_gravity = overlay_gravity_table.get(wm_gravity, 'x=main_w-overlay_w:y=0')
        if image_gravity:
            x, y = image_gravity.split(':')
            if wm_offsetx > 0:
                x += '+' + str(wm_offsetx)
            elif wm_offsetx < 0:
                x += str(wm_offsetx)

            if wm_offsety > 0:
                y += '+' + str(wm_offsety)
            elif wm_offsety < 0:
                y += str(wm_offsety)
            
            isOk = True
            print 'wmImage=%s' % wm_image
            try:
                wm_image_raw = urlsafe_base64_decode(wm_image)
            except Exception, e:
                print "wmImage is not base64 url safe encoding"
                isOk = False

            if type(wm_image_raw) == unicode:
                wm_image_raw = wm_image_raw.encode('utf-8')

            sep = '/'
            if wm_image_raw.startswith('/') or rootdir.endswith('/'):
                sep = ''

            #print 'rootdir type=', type(rootdir)
            #print 'sep type=', type(sep)
            #print 'wm_image_raw type=', type(wm_image_raw)
            
            image_str = '{}{}{}'
            image_abs_path = image_str.format(rootdir, sep, wm_image_raw)
            print 'image_abs_path=', image_abs_path, ',', type(image_abs_path)
            wm_image_raw = image_abs_path
            print 'after join root dir, wmImage= %s' % wm_image_raw

            if isOk:
                movie = 'movie=%s [wm_movie]' % wm_image_raw
                overlay = '[in][wm_movie] overlay=%s:%s' % (x, y)
                movie_and_overlay = '%s,%s' %(movie, overlay)
                watermark_filters.append(movie_and_overlay)

    if wm_text:
        wm_gravity_text = request.get('wmGravityText', 'NorthEast')
        wm_font = request.get('wmFont', '宋体')
        wm_fontcolor = request.get('wmFontColor', 'red')
        wm_fontsize = request.get('wmFontSize', 24)
        
        try:
            origine_wm_font = urlsafe_base64_decode(wm_font)
        except Exception, e:
            origine_wm_font = '宋体'
            logger.warning('wmFont is not base64 url safe encoding')

        isOk = True
        print 'wm_text=',wm_text,' type=', type(wm_text)
        try:
            origine_wm_text = urlsafe_base64_decode(wm_text)
        except Exception, e:
            logger.error('wmText is not base64 url safe encoding')
            isOk = False

        if isOk:
            if type(origine_wm_text) == unicode:
                origine_wm_text = origine_wm_text.encode('utf-8')
            print "wmtext=", origine_wm_text
        
            if type(wm_font) == unicode:
                wm_font = wm_font.encode('utf-8')

            if type(wm_fontcolor) == unicode:
                wm_fontcolor = wm_fontcolor.encode('utf-8')

            if type(wm_gravity_text) == unicode:
                wm_gravity_text = wm_gravity_text.encode('utf-8')

            if type(wm_fontsize) == unicode:
                wm_fontsize = wm_fontsize.encode('utf-8')
        
            fontfile_table = {'宋体':'/usr/share/fonts/fonts/zh_CN/TrueType/simsun.ttc',
            '黑体':'/usr/share/fonts/fonts/zh_CN/TrueType/simhei.ttf',
            '雅黑':'/usr/share/fonts/fonts/zh_CN/TrueType/msyh.ttf',
            '楷体':'/usr/share/fonts/fonts/zh_CN/TrueType/simkai.ttf',
            }

            fontfile = fontfile_table.get(origine_wm_font)
            if not fontfile:
                fontfile = '/usr/share/fonts/fonts/zh_CN/TrueType/simsun.ttc'
        
            drawtext_gravity_table = {'NorthWest':'x=0:y=0',
                'North':'x=(main_w-text_w)/2:y=0',
                'NorthEast':'x=main_w-text_w:y=0',
                'West':'x=0:y=(main_h-text_h)/2',
                'Center':'x=(main_w-text_w)/2:y=(main_h-text_h)/2',
                'East':'x=main_w-text_w:y=(main_h-text_h)/2',
                'SouthWest':'x=0:y=main_h-text_h',
                'South':'x=(main_w-text_w)/2:y=main_h-text_h',
                'SouthEast':'x=main_w-text_w:y=main_h-text_h',
            }

            text_gravity = drawtext_gravity_table.get(wm_gravity_text, 'x=main_w-text_w:y=0')

            drawtext = "drawtext=fontfile=%s:text='%s':%s:fontsize=%d:fontcolor=%s" %(fontfile, origine_wm_text, text_gravity, int(wm_fontsize), wm_fontcolor)
            print 'drawtext type=', type(drawtext)

            watermark_filters.append(drawtext)

    return watermark_filters


def transcode_request_to_convert_cmd(request, rootdir):
    """
    history:
    add rootdir parameter, because wmImage path is relative path, join rootdir to absolute path  2016-07-22 cwinging

    function:
    convert transcode cmd to Dict object
    { 
        'avthumb' : 'mp4',
        'ab' : '128k',
        'aq' : 3
        'ar' : 44100,
        'acodec' : 'libaac',
        'vcodec' : 'libx264'
    }
    to 
    {
        'format': 'mkv',
        'audio': {
            'codec': 'mp3',
            'samplerate': 11025,
            'channels': 2
        },
        'video': {
            'codec': 'h264',
            'width': 720,
            'height': 400,
            'fps': 15
            'filters' : 'overlay=main_w-overlay_w-5:5'
        }
    }
    """
    convert_cmd = {}
    format = request.get('avthumb', None)
    if not format:
        return
    convert_cmd['format'] = format

    if format == 'm3u8':
        hls = {}
        hls_time = request.get('segtime', 10)
        hls_segment_filename = request.get('pattern', None)
        hls['hls_time'] = hls_time
        convert_cmd['hls'] = hls
    pat = re.compile(r'(\d+)\D+')
    acodec = request.get('acodec', None)
    if acodec:
        audio = {}
        audio['codec'] = acodec
        channels = request.get('ac', None)
        ab = request.get('ab', None)
        aq = request.get('aq', None)
        ar = request.get('ar', None)

        if channels:
            audio['channels'] = channels
        if ab:
            audiobitrates = pat.findall(ab)
            audio['bitrate'] = audiobitrates[0]
        if aq:
            audio['quality'] = aq
        if ar:
            audio['samplerate'] = ar
        convert_cmd['audio'] = audio

    vcodec = request.get('vcodec', None)
    if vcodec:
        video = {}
        video['codec'] = vcodec
        bitrate = request.get('vb', None)
        fps = request.get('r', None)
        resolution = request.get('s', None)
        if resolution:
            width, height = resolution.split('x')
            video['width'] = width
            video['height'] = height

        if bitrate:
            videobitrates = pat.findall(bitrate)
            video['bitrate'] = videobitrates[0]

        if fps:
            video['fps'] = fps

        mode = 'stretch'
        autoscale = request.get('autoscale', None)
        if autoscale:
            mode = 'pad'
        video['mode'] = mode

        #watermark
        filters = get_watermark_ops(request, rootdir)
        sep = ''
        wm_filters = ''
        for wm_filter in filters:
            wm_filters += sep + wm_filter
            sep = ';'

        video['filters'] = wm_filters

        convert_cmd['video'] = video
    print convert_cmd
    return convert_cmd


def convert_target_template(input_file, root_dir, domain, target, request):
    """
    replace target template to real transcode filename
    ${filename}_${Resolution}_${vb}.${subffix}
    """
    input_basename = os.path.basename(input_file)
    input_dir = os.path.dirname(input_file)

    relative_path = input_file[len(root_dir):]
    relative_dir = os.path.dirname(relative_path)

    if domain.endswith(os.sep):
        domain = domain.rstrip(os.sep)

    filename, extension = os.path.splitext(input_basename)
    print '(%s %s)' %(filename, extension)
    resolution = request.get('s')
    if not resolution:
        resolution = ''
    
    vb = request.get('vb')
    if not vb:
        vb = ''
    
    target_filename = target.replace('${filename}', filename)
    if resolution:
        target_filename = target_filename.replace('${Resolution}', resolution)
    else:
        target_filename = target_filename.replace('_${Resolution}', resolution)

    if vb:
        target_filename = target_filename.replace('${vb}', vb)
    else:
        target_filename = target_filename.replace('_${vb}', vb)

    target_filename = target_filename.replace('.${subffix}', extension)

    target_full_filename = os.path.join(input_dir, target_filename)
    target_url = domain + os.path.join(relative_dir, target_filename)
    print 'target_full_name=%s, target_url=%s' %(target_full_filename, target_url)
    return target_full_filename, target_url


def http_get_transcode_request(mq_url):
    try:
        transcode_mq = urllib2.urlopen(mq_url, timeout=connect_timeout_in_second)
    except urllib2.URLError, e:
        logger.error('open httpmq ' + mq_url + ' failed, try again!')
        return None

    transcode_task_for_json = transcode_mq.read()
    if 'HTTPMQ_GET_END' in transcode_task_for_json:
        return None
    print 'raw task for json=',transcode_task_for_json
    
    try:
        transcode_req = json.loads(transcode_task_for_json)
    except:
        logger.error('decode json:' + transcode_task_for_json + ' failed')
        return None

    task_logger.debug('receive task:' + transcode_task_for_json)
    
    return transcode_req

def generate_nofity_request(id, input_key, args):
    """
    generate transcode notify json result
    @id : md5(scope+persistentOps) 
    @input_key: full source filename
    @args : list of tuple(cmd, code, desc, error, hash, key) 
    """
    notify_request = {}
    notify_request['id'] = id
    notify_request['inputKey'] = input_key
    items = []
    for arg in args:
        cmd, code, desc, error, hashcode, key = arg
        #fix up url is not url encoding, issue: http://192.168.1.46/zentao/bug-view-1723.html
        if key and not key.endswith('.m3u8'):
            print 'key=', key, 'type=', type(key)
            try:
                if type(key) == unicode:
                    key = key.encode('utf-8')
                key = urllib.quote(key, safe=':/')
            except Exception, e:
                logger.error('key quote failed, error:' + str(e))
                pass

        item = {}
        item['cmd'] = cmd
        item['code'] = code
        item['desc'] = desc
        item['error'] = error
        item['hash'] = hashcode
        item['key'] = key
        items.append(item)

    notify_request['items'] = items
    notify_request_json = json.dumps(notify_request)
    return notify_request_json

def generate_progress_request(id, progress):
    progress_request = {}
    progress_request['id'] = id
    progress_request['progress'] = int(progress)
    progress_request['desc'] = 'transcode progress: %d%%' %(int(progress))
    progress_info = json.dumps(progress_request)
    return progress_info

def http_post_transcode_notify(notify_url, notify_stats):
    """
    转码结果通知
    """
    try:
        print 'http post transcode status:', notify_stats
        req = urllib2.Request(notify_url, notify_stats, headers={'Content-type': 'application/json', 'Accept': 'application/json'})
        response = urllib2.urlopen(req, timeout=5)
        notify_reply = response.read()
        print notify_reply
    except (urllib2.URLError, Exception), e:
        logger.error('transcode notify failed, error:' + str(e))

def http_post_transcode_process(notify_url, progress_info):
    """
    转码进度通知
    """
    try:
        print 'http post transcode progress:', progress_info
        req = urllib2.Request(notify_url, progress_info, headers={'Content-type': 'application/json', 'Accept': 'application/json'})
        response = urllib2.urlopen(req, timeout=2)
        notify_reply = response.read()
        print notify_reply
    except (urllib2.URLError, Exception), e:
        logger.error('transcode notify failed, error:' + str(e))

def is_trancoding_now(filename):
    '''
    检测目标文件是否正在转码，通过比较文件最后修改时间来判断文件是否在连续更新中
    '''
    t1 = os.path.getmtime(filename)
    time.sleep(1)
    t2 = os.path.getmtime(filename)
    deta_t = t2 - t1
    if deta_t > 0.001:
        return True
    return False

def rename_target_file(target_file):
    '''
    防止多个进程同时写入，重命名转码目标文件
    '''
    target_basename = os.path.basename(target_file)
    target_dir = os.path.dirname(target_file)

    filename, extension = os.path.splitext(target_basename)
    random_id = uuid.uuid1()
    rename_filename = '%s_%s' %(filename, random_id.hex)
    rename_filename += extension
    rename_target_file = os.path.join(target_dir, rename_filename)
    print rename_target_file
    return rename_target_file


def ffmpeg_transcode(id_md5, scope, root_dir, domain, notify_url, progress_url, target, ops):
    try:
        transcode_request = parse_persistent_ops(ops)
        
        target_filename, target_url = convert_target_template(scope, root_dir, domain, target, transcode_request)
    
        convert_cmd = transcode_request_to_convert_cmd(transcode_request, root_dir)
    except Exception, e:
        logger.error("invalid request:" + unicode(e))
    
    # detect target file whether is writing, and rename the target filename
    if os.path.exists(target_filename):
        if is_trancoding_now(target_filename):
            target_filename =  rename_target_file(target_filename)

    #print 'convert cmd', convert_cmd
    
    #transcoding ......
    try:
        c = Converter()
        info = c.probe(scope)
        duration = 1
        if info:
            if info.format:
                duration = info.format.duration
        conv = c.convert(scope, target_filename, convert_cmd)
    except (ValueError, ConverterError, FFMpegError, FFMpegConvertError), e:
        converterror = 'convert faild, error: %s' % unicode(e)
        logger.error(converterror)
        notify_quest = generate_nofity_request(id_md5, scope, [(ops, 3, 'transcode failed 1',unicode(e), '', target_url),])
        http_post_transcode_notify(notify_url, notify_quest)
        
        try:
            os.unlink(target_filename)
        except:
            pass

        return
    
    progress_steps = (int(duration) + 899) / 900 * 5
    progress_interval = int(100 / progress_steps)
    print 'file=%s, duration=%f, steps=%d, interval=%d' %(scope, duration, progress_steps, progress_interval)
    last_timecode = 0
    last_log_timecode = 0

    # progress 0%, means by start transcoding
    progress_info = generate_progress_request(id_md5, 0)
    http_post_transcode_process(progress_url, progress_info)

    try:
        for timecode in conv:
            if timecode - last_log_timecode >= 2.0:
                print "Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode)
                task_logger.debug("Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode))
                last_log_timecode = timecode
            
            if timecode - last_timecode >= progress_interval:
                progress_info = generate_progress_request(id_md5, timecode)
                #print progress_info
                http_post_transcode_process(progress_url, progress_info)
                last_timecode = timecode

    except Exception, e:
        converterror = 'transcode faild, error: %s' % unicode(e)
        logger.error(converterror)
        notify_quest = generate_nofity_request(id_md5, scope, [(ops, 3, 'transcode failed 2',unicode(e), '', target_url),])
        http_post_transcode_notify(notify_url, notify_quest)
        
        try:
            os.unlink(target_filename)
        except:
            pass
        
        return
     
    """
    for timecode in conv:
        print "Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode)
        task_logger.debug("Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode))
    """
    
    print "Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, 100.00)
    task_logger.debug("Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, 100.00))

    # progress 100%, means by transcoding complete
    progress_info = generate_progress_request(id_md5, 100)
    http_post_transcode_process(progress_url, progress_info)

    notify_quest = generate_nofity_request(id_md5, scope, [(ops, 0, 'transcode succefully','', '', target_url),])
    http_post_transcode_notify(notify_url, notify_quest)


def transocde_worker_process(mq_url, notify_url, progress_url):
    p = multiprocessing.current_process()
    print 'transcode worker process name:', p.name, " pid:", p.pid
    while True:
        time.sleep(2)
        #print 'http get transcode task queue:', mq_url
        transcode_req = http_get_transcode_request(mq_url)
        if not transcode_req:
            continue

        print 'worker:',p.name,',transcode request:', transcode_req

        try:
            scope = transcode_req.get('scope', None)
            if not scope:
                logger.error('transcode request has not "scope" filed')
                continue    

            ops = transcode_req.get('persistentOps', None)
            if not ops:
                logger.error('worker:'+p.name+',transcode request has not "persistentOps" filed')
                continue

            print 'persistentOps:', ops
            if not ops.startswith('avthumb/'):
                logger.error('worker:'+p.name+',invalid persistentOps:' + ops)
                continue

            target = transcode_req.get('targetTemplate')
            if not target:
                target = '${filename}_${Resolution}_${vb}.${subffix}'

        
            print 'scope=%s , ops=%s, target=%s' % (scope, ops, target)
        
            root_dir = transcode_req.get('rootDir', None)
            if not root_dir:
                root_dir = ''

            task_id = transcode_req.get('taskID', None)
            if not task_id:
                logger.error('worker:'+p.name+',invalid taskID:')
                continue
        except:
            continue

        print 'taskID=', task_id

        #获取用户域名信息,缺省伪源nginx分发服务器地址
        domain = transcode_req.get('domain', None)
        if not domain:
            domain = default_nginx_addr

        #my_scope = scope + ops
        #if type(my_scope) == unicode:
        #    my_scope = my_scope.encode('utf-8')   

        #m = md5.new()
        #m.update(my_scope)
        #id_md5 = m.hexdigest()


        if ';' in ops:
            cmds = ops.split(';')
            for cmd in cmds:
                ffmpeg_transcode(task_id, scope, root_dir, domain, notify_url, progress_url, target, cmd)
        else:
            ffmpeg_transcode(task_id, scope, root_dir, domain, notify_url, progress_url, target, ops)

class TranscodeDaemon(Daemon):
    def __init__(self,  pidfile, httpmq, notify_url, progress_url, cpus=1, level=logging.DEBUG, log=default_log, task_log=default_tasklog, stdin=os.devnull,
                 stdout=os.devnull, stderr=os.devnull,
                 home_dir='.', umask=022, verbose=1, use_gevent=False):
        super(TranscodeDaemon, self).__init__(pidfile, stdin, stdout, stderr, home_dir, umask, verbose, use_gevent)
        self.httpmq = httpmq
        self.notify_url = notify_url
        self.progress_url = progress_url
        self.cpus = cpus
        self.level = level
        self.log = log
        self.task_log = task_log

    def run(self):
        init_logger(logger,self.level, self.log)
        init_logger(task_logger, logging.DEBUG, self.task_log)
        workers = []
        for i in range(self.cpus):
            worker= multiprocessing.Process(name='transcode_woker_' + str(i), target=transocde_worker_process, args=(self.httpmq, self.notify_url, self.progress_url))
            worker.daemon = True
            workers.append(worker)

        #while True:
        try:
            for worker in workers:
                worker.start()

            for worker in workers:
                worker.join()
        except Exception, e:
            logger.error('transcode worker exited, error=' + str(e))

def main():
    parser = argparse.ArgumentParser(prog='transcode server arguments parser', conflict_handler='resolve')
    parser.add_argument('-c', '--conf', help='specify transcode server configer file')
    parser.add_argument('-f', '--frontend', action='store_true', default=False)
    args = parser.parse_args()
    transcode_configer = args.conf
    frontend = args.frontend

    if not transcode_configer:
        transcode_configer = 'transcode.cfg'
    
    #get httpmq , log, directory root path
    httpmq_url_new, log, log_level, task_log, pidfile, notify_url, progress_url = read_config(transcode_configer)
    if not httpmq_url_new:
        httpmq_url_new = httpmq_url

    if not log:
        log = default_log

    if not task_log:
        task_log = default_tasklog

    if not pidfile:
        pidfile = default_pidfile

    level = get_log_level(log_level)

    #init_logger(logger,level, log)
    #init_logger(task_logger, logging.DEBUG, task_log)
    cpus = multiprocessing.cpu_count()
    print 'system info, cpu count:', cpus
    if cpus < 1:
        cpus = 1

    transcode_server = TranscodeDaemon(pidfile, httpmq_url_new, notify_url, progress_url, cpus, level, log, task_log)
    if frontend:
        transcode_server.run()
    else:
        transcode_server.start()
    
if __name__ == '__main__':
    main()