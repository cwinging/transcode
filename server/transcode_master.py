#!/usr/bin/python
# encoding:utf-8

import multiprocessing
from converter import Converter
from converter import ConverterError,FFMpegConvertError,FFMpegError
import os.path
import math
import md5
import transcode_util

const_transcode_init_state = 0
const_transcode_slice_state = 1
const_transcode_running_state = 2
const_transcode_concat_state = 4
const_transcode_finish_state = 8


class TranscodeMaster(multiprocessing.Process):
    def __init__(self, logger, task_logger, task_queue, result_queue, mq_url, notify_url, progress_url, cpu_counts):
        super(TranscodeMaster, self).__init__(name='transcode master process')
        self.logger = logger
        self.task_logger = task_logger
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.mq_url = mq_url
        self.notify_url = notify_url
        self.progress_url = progress_url
        self.cpu_counts = cpu_counts
        # save taskid-subid map
        # transcode_tasks locker
        self.tasks_lock = multiprocessing.Lock()
        # task contains taskid/subids map
        self.transcode_tasks = {}
        # task status locker
        self.task_status_lock = multiprocessing.Lock()
        # task status contains task status for taskid or subid
        self.transcode_task_status = {}
        #
        self.main_task_cond = multiprocessing.Condition()
        #
        self.transcode_main_tasks = {}

    def run(self):
        """
        master进程
        1.主进程从httpmq获取转码任务,负责切片和分发任务
        2.转码通知监听线程，负责维护转码任务及子任务状态，上报转码结果及进度
        """
        while True:
            # wati for length of transcode_main_tasks is less than cup counts
            with self.main_task_cond:
                while( len(self.transcode_main_tasks) > self.cpu_counts)
                    self.main_task_cond.wait()

            #print 'http get transcode task queue:', mq_url
            transcode_req = transcode_util.http_get_transcode_request(self.mq_url)
            if not transcode_req:
                continue

            print 'worker:',p.name,',transcode request:', transcode_req
            
            scope = transcode_req.get('scope', None)
            if not scope:
                logger.error('transcode request has not "scope" filed')
                continue    

            ops = transcode_req.get('persistentOps', None)
            if not ops:
                logger.error('worker:'+p.name+',transcode request has not "persistentOps" filed')
                continue

            print 'persistentOps:', ops
            if not ops.startswith('avthumb/') and not ops.startswith('avconcat/'):
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

            print 'taskID=', task_id
            #获取用户域名信息,缺省伪源nginx分发服务器地址
            domain = transcode_req.get('domain', None)
            if not domain:
                domain = default_nginx_addr

            self.transcode_slice(transcode_req)
        

    def transcode_slice_i(self, taskid, filename, ops):
        """
        将转码任务切分成多个转码任务
        @param taskid 转码任务ID
        @param filename 转码视频文件
        @param ops 转码参数
        @return 返回多个转码任务 
        {   
            taskid:'', 任务ID 
            subid:'',  子任务ID
            ops:''     子任务转码参数
        }
        """
        if not os.path.exists(filename):
            print "input file does't exist:", filename
            self.logger.error('input file ' + filename + ' does not exist')
            return 0, None, None

        try:
            c = Converter()
            info = c.probe(scope)
            duration = 0
            if info:
                if info.format:
                    duration = info.format.duration
        except (ValueError, ConverterError, FFMpegError, FFMpegConvertError), e:
            converterror = 'probe faild, error: %s' % unicode(e)
            self.logger.error(converterror)
            return 0, None, None
        
        if duration <= 0:
            return 0, None, None

        # set 5 minutes(300s) per slice file
        slice_step = 300.0
        slice_counts = math.ceil(duration / slice_step)

        transcode_slice_ops = []
        slice_durations = []
        for i in range(slice_counts):
            slice_ops = ''
            if i != slice_counts-1:
                slice_ops = '%s/ss/%f/to/%f' %(ops, i*slice_step, slice_step)
                slice_durations.append(slice_step)
            else:
                slice_ops = '%s/ss/%f' %(ops, i*slice_step)
                slice_durations.append(duration - i*slice_step)

            transcode_slice_ops.append(slice_ops)

        return duration, transcode_slice_ops, slice_durations
    
    def generate_transcode_subid(self, ops):
        m = md5.new()
        m.update(ops)
        return m.hexdigest()

    def transcode_task_status_create(self, id, ops, outfile, duration):
        task_status = {}
        task_status['id'] = id
        task_status['persistentOps'] = ops
        task_status['code'] = -1
        task_status['desc'] = 'init status'
        task_status['duration'] = duration
        task_status['timecode'] = 0.0
        task_status['progress'] = 0
        task_status['outfile'] = outfile
        task_status['notify'] = 0
        task_status['status'] = 0
        return task_status

    def transcode_main_task_create(self, taskid, target_filename, format, task):
        main_task = {}
        main_task['id'] = taskid
        main_task['outfile'] = target_filename
        main_task['format'] = format
        main_task['task'] = task
        return main_task

    def transcode_slice(self, transcode_req):
        infile = transcode_req.get('scope', None)
        if not infile:
            raise Exception('transcode task has none scope value')
        
        taskid = transcode_req.get('taskID', None)
        if not taskid:
            raise Exception('transcode task have none taskID value')

        ops = transcode_req.get('persistentOps', None)
        if not ops:
            raise Exception('transcode task have none persistentOps value')

        domain = transcode_req.get('domain', None)
        if not domain:
            domain = 'nginx server ip'

        root_dir = transcode_req.get('rootDir', None)
        if not root_dir:
            raise Exception('transcode task has none rootDir value')

        duration, sliceOpsList, slice_durations = self.transcode_slice_i(taskid, infile, ops)
        if len(sliceOpsList) == 0:
            raise Exception('transode slice failed')

        # get input file basename; dir path; filename; extension
        infile_basename = os.path.basename(infile)
        infile_dir = os.path.dirname(infile)
        filename, extension = os.path.splitext(infile_basename)

        transcode_request = self.parse_persistent_ops(ops)
        target_file, target_url = convert_target_template(scope, root_dir, domain, target, transcode_request)
        
        subtasks = []
        for i, sliceOps in enumerate(sliceOpsList):
            # generate transcode sub task
            transcode_req_copy = transcode_req.copy()
            transcode_req_copy['persistentOps'] = sliceOps
            subid = self.generate_transcode_subid(sliceOps)
            transcode_req_copy['subid'] = subid
            # gererate the full path of a slice
            outfile = '%s_%d%s' % (filename, i, extension)
            full_outfile_path = os.path.join(infile_dir, outfile)
            transcode_req_copy['targetTemplate'] = full_outfile_path

            # add subid
            subtasks.extend(subid)

            # generate subtask info
            transcode_subtask = self.transcode_task_status_create(subid, sliceOps, full_outfile_path, slice_durations[i])
            self.task_status_lock.acquire()
            self.transcode_task_status[subid] = transcode_subtask
            self.task_status_lock.release()

            # insert a transcode subtask to taskqueue
            self.task_queue.put(transcode_req_copy)
        
        self.tasks_lock.acquire()
        self.transcode_tasks[taskid] = subtasks
        self.tasks_lock.release()

        self.task_status_lock.acquire()
        self.transcode_task_status[taskid] = self.transcode_task_status_create(taskid, ops, target_file, duration)
        self.task_status_lock.release()

        with self.main_task_cond:
            self.transcode_main_tasks[taskid] = self.transcode_main_task_create(taskid, format, target_file, target_url, transcode_req)
           

    def transcode_concat(self, transcode_req):
        """
        将多个切片转码文件合片任务生成
        """
        ops = transcode_req.get('persistentOps', None)
        if not ops:
            self.logger.error('transcode task have none persistentOps value')
            return

        transcode_cmd_request = parse_persistent_ops(ops)
        format = transcode_cmd_request.get('avthumb', None)
        if not format:
            self.logger.error('transcode task have none format value')
            return

        taskid = transcode_req.get('taskID', None)
        if not taskid:
            self.logger.error('transcode task have none taskID value')
            return

        main_task = self.transcode_main_tasks.get(taskid, None)
        if not main_task:
            self.logger.error('main task queue have none taskid=%s' % taskid)
            return

        target_file = main_task.get('outfile', None)
        if not target_file:
            self.logger.error('main taskid=$s have none outfile value' % taskid)
            return

        slash = '/'
        concat_persistentOps = 'concat/2/format/%s' % format

        subtasks = self.transcode_tasks.get(taskid, None)
        if not subtasks:
            self.logger.error('taskid=%s have none subtasks' % taskid)
            return
        
        for subid in subtasks:
            subtask = self.transcode_subtasks.get(subid, None)
            if not subtask:
                continue

            outfile = subtask.get('outfile', None)
            if not outfile:
                continue

            if type(outfile) == unicode:
                outfile = outfile.encode('utf-8')
            concat_persistentOps = '%s/%s' % (concat_persistentOps, urlsafe_base64_encode(outfile))
        
        subid = self.generate_transcode_subid(concat_persistentOps)
        transcode_req['persistentOps'] = concat_persistentOps
        transcode_req['targetTemplate'] = outfile
        transcode_req['subid'] = subid
        # send concat request to task_queue
        self.task_queue.put(transcode_req)

        self.transcode_tasks[taskid].extend([subid])
        self.transcode_subtasks[subid] = self.transcode_subtask_create(subid, concat_persistentOps, outfile)

        main_task = self.transcode_task_status.get(taskid, None)
        if not main_task:
            return
        main_task['status'] = const_transcode_concat_state

    def task_notify_thread(self, queue):
        """
        接收转码结果通知
        @param queue: result_queue
        """
        while True:
            result = queue.get()
            cmd = result.get('cmd', None)
            if cmd is None:
                continue

            if cmd == 'result':
                self._handle_result(result)
            elif cmd == 'progress':
                self._handle_progress(result)
            else:
                print 'unknow notify result,', result
                continue

    def handle_result(self, result):
        """
        处理转码结果上报
        @param result: 转码结果
        """
        info = result['info']
        taskid = info['taskid']
        subid = info['subid']
        result_code = info['code']
        result_desc = info['desc']

        if result_code == 0:
            self.handle_failed_result(taskid, subid, code, desc)
        else:
            self.handle_success_result(taskid, subid, code, desc)

    def handle_failed_result(self, taskid, subid, code, desc):
        """
        处理转码失败上报结果
        @step1 设置转码状态和发送状态
        @step2 发送转码失败结果通知
        @step3 删除任务和所有子任务
        """
        with self.task_status_lock:
            task = self.transcode_task_status.get(subid, None)
            if not task:
                self.logger.error('main task queue has none taskid=%s' % taskid)
                return
            task['code'] = code
            task['desc'] = desc
            task['notify'] = 1
            task['status'] = const_transcode_finish_state


            main_task = self.transcode_task_status.get(taskid, None)
            if not main_task:
                return
            main_task['code'] = code
            main_task['desc'] = desc
            main_task['notify'] = 1
            main_task['status'] = const_transcode_finish_state

        notify_info = transcode_util.generate_nofity_request(taskid, code, desc)
        transcode_util.http_post_transcode_notify(notify_url, notify_info)

        # setp3 remove taskid and all subids
        with self.tasks_lock:
            subtasks = self.transcode_tasks.get(taskid, None)
            del self.transcode_tasks[taskid]
    
        with self.task_status_lock:
            for sub in subtasks:
                del self.transcode_task_status[sub]

        with self.main_task_cond:
            del self.transcode_main_tasks[taskid]
            self.main_task_cond.notify()


    def handle_success_result(self, taskid, subid, code, desc):
        """
        处理转码成功上报结果
        @step1 更新对应subid的子任务状态
        @step2 上报当次转码进度
        @step3 检测所有子任务是否完成，未完成则跳出执行
        @step4 更新主任务状态
        @step5 上报转码结果
        """
        # step1
        self.task_status_lock.acquire()
        task = self.transcode_task_status.get(subid, None)
        if not task:
            self.logger.error('main task queue has none taskid=%s' % taskid)
            self.task_status_lock.release()
            return
        
        task['code'] = code
        task['desc'] = desc
        task['notify'] = 1
        task['status'] = const_transcode_finish_state
        task['timecode'] = task['duration']
        self.task_status_lock.release()

        # step2
        subtasks = self.transcode_tasks.get(taskid, None)
        if not subtasks:
            return
        
        totals = 0.0
        finished_num = 0
        for sub in subtasks:
            self.task_status_lock.acquire()
            task = self.transcode_task_status.get(subid, None)
            self.task_status_lock.release()
            if not task:
                continue
            totals += task['timecode']
            if task['code'] == 1:
                finished_num++
        
        #step3
        if finished_num < len(subtasks):
            return

        #step4
        self.task_status_lock.acquire()
        main_task = self.transcode_task_status.get(taskid, None)
        if not main_task:
            self.task_status_lock.release()
            return
        
        if main_task['status'] <= const_transcode_running_state:
            self.transcode_concat(transcode_req)
            # should update status in concat function
        else:
            main_task['code'] = 1
            main_task['desc'] = 'transcode successfully'
            main_task['notify'] = 1
            main_task['status'] = const_transcode_finish_state
            self.task_status_lock.release()
            
            # send transcode notify and 100% progress
            notify_request = generate_nofity_request(taskid, code, desc)
            http_post_transcode_notify(notify_url, notify_request)

            progress_info = generate_progress_request(taskid, 100)
            http_post_transcode_process(progress_url, progress_info)


    def handle_progress(self, progress):
        """
        处理转码进度上报
        @param progress: 转码进度上报
        @step1 更新子任务的进度和时间码
        @step2 上报任务进度
        """
        info = progress['info']
        taskid = info['taskid']
        subid = info['subid']
        progress = info['progress']
        timecode = info['timecode']

        #step1 update progress and timecode in subtask
        self.task_status_lock.acquire()
        task = self.transcode_task_status.get(subid, None)
        if not task:
            self.task_status_lock.release()
            return
        task['progress'] = progress
        task['timecode'] = timecode
        self.task_status_lock.release()

        #step2
        subtasks = self.transcode_tasks.get(taskid, None)
        if not subtasks:
            return
        
        timecode_totals = 0.0
        for sub in subtasks:
            self.task_status_lock.acquire()
            task = self.transcode_task_status.get(subid, None)
            self.task_status_lock.release()
            if not task:
                continue
            timecode_totals += task['timecode']

        self.task_status_lock.acquire()
        main_task = self.transcode_task_status.get(subid, None)
        self.task_status_lock.release()
        if not main_task:
            return

        duration = main_task['duration']
        if duration <= 0
            duration = 1.0
        total_progress = math.floor(timecode_totals * 100 / duration)

        progress_info = generate_progress_request(taskid, total_progress)
        http_post_transcode_process(progress_url, progress_info)

