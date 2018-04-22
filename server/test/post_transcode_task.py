# encoding:utf-8

import json
import urllib
import urllib2
import base64
import argparse

url = "http://172.16.23.208:9000/?charset=utf-8&name=transcodequeue&opt=put&auth=abc"
default_png = '/home/1.png'
container_forma_tuple = ('.mp4', '.ts', '.mp3', '.mkv', '.flv', '.f4v', '.avi', '.mpg', '.mpeg', '.dat', '.vob', '.3gp', '.mov')

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
    print 'decode base64 string=%s' % string
    return base64.urlsafe_b64decode(string)

def main():
    parser = argparse.ArgumentParser(prog='transcode task request client', conflict_handler='resolve')
    parser.add_argument('-t', '--templatefile', help='transcode template file')
    parser.add_argument('-p','--pngimage' ,help='png path')
    parser.add_argument('-text', help='matermark text')
    args = parser.parse_args()
    templatefile = args.templatefile
    wm_png = args.pngimage
    wm_text = args.text

    task_for_json = None
    with open(templatefile, 'r+',) as tf:
        task_for_json = tf.read()
    
    print 'template:', task_for_json

    #if type(task_for_json) == unicode:
    #    task_for_json = task_for_json.encode('utf-8')

    my_transcode_task = task_for_json

    transcode_request = json.loads(task_for_json)
    transcode_ops = transcode_request.get('persistentOps')
    
    if wm_png:
        if type(wm_png) == unicode:
            wm_png = wm_png.encode('utf-8')

        watermark_png = urlsafe_base64_encode(wm_png)
        transcode_ops = transcode_ops.replace('${png}', watermark_png)

    if wm_text:
        if type(wm_text) == unicode:
            wm_text = wm_text.encode('utf-8')
            
        watermark_text = urlsafe_base64_encode(wm_text)
        transcode_ops = transcode_ops.replace('${text}', watermark_text)

    transcode_request['persistentOps'] = transcode_ops
    my_transcode_task = json.dumps(transcode_request)
              
    req = urllib2.Request(url, my_transcode_task, headers={'Content-type': 'application/json', 'Accept': 'application/json'})
    response = urllib2.urlopen(req)
    response_content = response.read()
    print response_content

if __name__ == '__main__':
    main()