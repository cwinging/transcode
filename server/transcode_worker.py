#!/usr/bin/python
# encoding:utf-8

import multiprocessing
import time

const_transcode_avthumb = 1
const_transcode_avconcat = 2

class TranscodeWorker(multiprocessing.Process):
    """
    转码工作进程，负责转码切分文件
    """
    def __init__(self, procname, logger, task_logger, task_queue, result_queue):
        super(TranscodeWorker, self).__init__(name=procname)
        self.logger = logger
        self.task_logger = task_logger
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        while True:
            try:
                self.transocde_worker_process(self.task_queue, self.result_queue)
            except Exception, e:
                self.logger.error('transcode_worker: ' + self.name + ' fatal errors:' + unicode(e))
    
    def get_transcode_request(self, queue):
        """
        从任务列队中获取转码任务
        @queue task_queue
        """
        transcode_task_for_json = queue.get()
        print 'acquire raw task for json=',transcode_task_for_json
    
        try:
            transcode_req = json.loads(transcode_task_for_json)
        except:
            self.logger.error('decode json:' + transcode_task_for_json + ' failed')
            return None

        self.task_logger.debug('receive task:' + transcode_task_for_json)    
        return transcode_req

    def transocde_worker_process(self, task_queue, result_queue):
    	"""
    	从transcode_task_queue获取转码任务，执行转码并上报转码结果
    	@queue transcode_task_queue队列，master进程推送转码任务，worker进程获取转码任务
    	@result_queue transcode_result_queue队列，worker进程上报转码结果
    	"""
        p = multiprocessing.current_process()
        print 'transcode worker process name:', p.name, " pid:", p.pid
        while True:
            time.sleep(2)
            #print 'http get transcode task queue:', mq_url
            transcode_req = self.get_transcode_request(self.task_queue)
            if not transcode_req:
                continue

            print 'worker:',p.name,',transcode request:', transcode_req

            try:
                scope = transcode_req.get('scope', None)
                if not scope:
                    self.logger.error('transcode request has not "scope" filed')
                    continue    

                ops = transcode_req.get('persistentOps', None)
                if not ops:
                    self.logger.error('worker:'+p.name+',transcode request has not "persistentOps" filed')
                    continue

                print 'persistentOps:', ops
                transcode_type = const_transcode_avthumb
                if ops.startswith('avthumb/'):
                    transcode_type = const_transcode_avthumb
                elif ops.startswith('avconcat/'):
                    transcode_type = const_transcode_avconcat
                else:
                    self.logger.error('worker:'+p.name+',invalid persistentOps value')
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
                    self.logger.error('worker:'+p.name+',invalid taskID:')
                    continue
            except:
                continue

            print 'taskID=', task_id

            #获取用户域名信息,缺省伪源nginx分发服务器地址
            domain = transcode_req.get('domain', None)
            if not domain:
                domain = default_nginx_addr


            if ';' in ops:
                cmds = ops.split(';')
                for cmd in cmds:
                    self.ffmpeg_transcode(task_id, scope, root_dir, domain, notify_url, progress_url, target, cmd, transcode_type)
            else:
                self.ffmpeg_transcode(task_id, scope, root_dir, domain, notify_url, progress_url, target, ops, transcode_type)
    

    def ffmpeg_transcode(self, taskid, subid, scope, root_dir, domain, notify_url, progress_url, target, ops, avopt):
        if avopt == const_transcode_avconcat:
            """
            视频拼接处理
            """
            pass
        else:
            """
            视频转码处理
            """
            try:
                transcode_request = self.parse_persistent_ops(ops)
                target_filename, target_url = self.convert_target_template(scope, root_dir, domain, target, transcode_request)
                convert_cmd = self.transcode_request_to_convert_cmd(transcode_request, root_dir)
            except Exception, e:
                self.logger.error("invalid request:" + unicode(e))
        
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
                converterror = u'convert faild, error: %s' % unicode(e)
                self.logger.error(converterror)
                transcode_result = self.generate_transcode_result(taskid, subid, 0)
                self.submit_transcode_result(transcode_result)        
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
            progress_info = self.generate_transcode_progress(taskid, subid, 0, 0.0)
            self.submit_transcode_progress(progress_info)

            try:
                for (timecode, time) in conv:
                    if timecode - last_log_timecode >= 2.0:
                        print "Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode)
                        self.task_logger.debug("Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, timecode))
                        last_log_timecode = timecode
                
                    if timecode - last_timecode >= progress_interval:
                        progress_info = self.generate_transcode_progress(taskid, subid, timecode, time)
                        self.submit_transcode_progress(progress_info)
                        last_timecode = timecode

            except Exception, e:
                converterror = u'transcode faild, error: %s' % unicode(e)
                self.logger.error(converterror)
                transcode_result = self.generate_transcode_result(taskid, subid, 0)
                self.submit_transcode_result(transcode_result)   
            
                try:
                    os.unlink(target_filename)
                except:
                    pass
            
                return
             
            print "Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, 100.00)
            self.task_logger.debug("Converting %s to %s (%.2f%%) ...\r" % (scope, target_filename, 100.00))

            # progress 100%, means by transcoding complete
            progress_info = self.generate_transcode_progress(taskid, subid, 100, time)
            self.submit_transcode_progress(progress_info)
            
            # transcode successfully, result_code be seted to 1
            transcode_result = self.generate_transcode_result(taskid, subid, 1)
            self.submit_transcode_result(transcode_result)
    
    def generate_transcode_result(self, taskid, subid, result_code, desc):
        """
        生成转码结果通知
        @taskid 任务ID
        @subid  切片转码任务ID
        @result_code 转码结果 0失败 1成功
        {
           'cmd' : 'result' or 'progress',
           'info' : {
                'taskid' : '',
                'subid' : '', 
                'code' : 1,
                'progress' : 20,
                'timecode' : 13.56 
           }
        }
        """
        result = {}
        result['cmd'] = 'result'
        info = {}
        info['taskid'] = taskid
        info['subid'] = subid
        info['code'] = result_code
        info['desc'] = desc
        result['info'] = info
        result_json = json.dumps(result)
        return result_json


    def generate_transcode_progress(self, taskid, subid, progress, timecode):
        """
        生成转码进度通知
        @taskid 任务ID
        @subid  切片转码任务ID
        @progress 转码进度百分比，取整
        @timecode 转码进度时间轴刻度，双精度浮点数
        """
        result = {}
        result['cmd'] = 'progress'
        info = {}
        info['taskid'] = taskid
        info['subid'] = subid
        info['progress'] = progress
        info['timecode'] = timecode
        result['info'] = info
        result_json = json.dumps(result)
        return result_json

    def submit_transcode_result(self, result):
        self.result_queue.put(result)

    def submit_transcode_progress(self, progress):
        self.result_queue.put(progress)

    def parse_persistent_ops(self, cmd):
        """
        convert persistentOps to dict
        转换persistentOps为键值对形式
        """
        cmd_argv = cmd.split('/')
        files = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 == 0]
        values = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 != 0]
        request = dict(zip(files, values))
        return request

    def get_watermark_ops(self, request, rootdir):
        """
        get watermark filters from request
        产生水印fiter参数
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
                self.logger.warning('wmFont is not base64 url safe encoding')

            isOk = True
            print 'wm_text=',wm_text,' type=', type(wm_text)
            try:
                origine_wm_text = urlsafe_base64_decode(wm_text)
            except Exception, e:
                self.logger.error('wmText is not base64 url safe encoding')
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


    def transcode_request_to_convert_cmd(self, request, rootdir):
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


    def convert_target_template(self, input_file, root_dir, domain, target, request):
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
