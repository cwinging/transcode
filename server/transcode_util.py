#!/usr/bin/python
# encoding:utf-8

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

def parse_persistent_ops(cmd):
    """
    convert persistentOps to dict
    """
    cmd_argv = cmd.split('/')
    files = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 == 0]
    values = [cmd_argv[i] for i in range(len(cmd_argv)) if i%2 != 0]
    request = dict(zip(files, values))
    return request

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


def http_get_transcode_request(mq_url, logger, task_logger):
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

def generate_nofity_request(id, input_key, args, logger):
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

def http_post_transcode_notify(notify_url, notify_stats, logger):
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

def http_post_transcode_process(notify_url, progress_info, logger):
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
