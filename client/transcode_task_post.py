#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
转码任务推送工具:
功能：扫描指定目录，对每个转码文件向转码服务网关发起转码请求

说明：需要客户在自己机器上做ftp目录的镜像目录

命令行参数：
-prefix: 客户机器的镜像目录相对于ftp服务上的路径
-d:指定需要扫描的目标目录，相当于ftp服务上需要转码的镜像目录
-u:用户ftp服务的用户名
-p:用户ftp登陆密码
-t:待转码的策略模板文件
-url:转码任务网关,对用户转码请求鉴权认证
"""

import argparse
import os
import os.path
import json
import urllib
import urllib2
import base64
import locale

container_forma_tuple = ('.mp4', '.ts', '.mp3', '.mkv', '.flv', '.f4v', '.avi', '.mpg', '.mpeg', '.dat', '.vob', '.3gp', '.mov')
console_encoding = locale.getdefaultlocale()[1] or 'utf-8'
print console_encoding

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

def parse_transcode_template(templatefile):
    with open(templatefile, 'r') as tf:
        content = tf.read()
        #print 'template file content:', content
        try:
            t = json.loads(content)
        except Exception, e:
            t = None
        return t

def http_post_transcode_task(url, body, user, passwd):
    """
    http post transcode task to trancode gateway server
    """
    req = urllib2.Request(url, body, headers={'Content-type': 'application/json', 'Accept': 'application/json'})
    #auth = base64.encodestring('%s:%s' % (user, passwd))[:-1]
    #authheader =  "Basic %s" % auth
    #req.add_header("Authorization", authheader)

    try:
        response = urllib2.urlopen(req)
        if response.code != 200:
            print 'http post %s , transcode task: %s failed.' % (url, body)
        else:
            print 'http post transcode task response:', response.read()
    except urllib2.URLError, e:
        print 'http post transcode task failed, error:', e


def browse_dir_for_transcode(current_dir, prefix, url, png, text, template, user, password):
    #get absolute directory path
    full_dir = current_dir
    if not os.path.isabs(current_dir):
        full_dir = os.path.realpath(current_dir)

    complete_table = {}
    complete_text_path = full_dir + os.sep + 'complete.txt'
    try:
        with open(complete_text_path, 'r+') as complete_f:
            for line in complete_f:
                complete_table[line.strip()] = True
    except:
        pass

    complete_file = open(complete_text_path, 'a+')
    if png:
        if type(png) == unicode:
            png = png.encode('utf-8')
        png_base64_url_safe = urlsafe_base64_encode(png)

    if text:
        if type(text) == unicode:
            text = text.encode('utf-8')
            print 'text1=',text
        text_base64_url_safe = urlsafe_base64_encode(text)
        print 'text base64=', [text_base64_url_safe]

    for root, dirs, files in os.walk(full_dir): 
        for f in files:
            full_path = os.path.join(root, f)
            print 'file:', full_path
            fname, ext = os.path.splitext(f)
            if ext.lower() in container_forma_tuple:
                #video or audio file container
                valid_path = full_path[len(full_dir)+1:]
                if not prefix.endswith(os.sep):
                    prefix += '/'

                real_file_path = prefix + valid_path
                print 'real file path=',real_file_path
                template['scope'] = real_file_path

                if png:
                    ops = template['persistentOps']
                    ops = ops.replace('${png}', png_base64_url_safe)
                    template['persistentOps'] = ops

                if text:
                    ops = template['persistentOps']
                    ops = ops.replace('${text}', text_base64_url_safe)
                    template['persistentOps'] = ops              
                 
                if f in complete_table:
                    continue
                
                print 'task:', json.dumps(template)
                http_post_transcode_task(url, json.dumps(template), user, password)
                complete_file.write(f+'\n')

    complete_file.close()
                                

def main():
    parser = argparse.ArgumentParser(prog='transcode task request client', conflict_handler='resolve')
    parser.add_argument('-t', '--templatefile', help='transcode template file')
    parser.add_argument('-u', '--user', help='user name')
    parser.add_argument('-p', '--password', help='password')
    parser.add_argument('-d', '--directory', help='directory for want to transcode')
    parser.add_argument('-prefix', help='prefix path for directory that want to transcode in ftp server')
    parser.add_argument('-url', help='http transcode gateway url')
    parser.add_argument('-png', help='png file that add watermark to video')
    parser.add_argument('-text', help='text content that add watermark to video')
    args = parser.parse_args()

    user = args.user
    password = args.password
    templatefile = args.templatefile
    url = args.url
    prefix = args.prefix
    current_dir = args.directory
    png = args.png
    text = args.text
    gbk_text = ''

    if text:
        gbk_text = text.decode(console_encoding)

 
    template = parse_transcode_template(templatefile)
    if not template:
        print 'transcode file: %s is invalid' % templatefile
        return
    
    browse_dir_for_transcode(current_dir, prefix, url, png, gbk_text, template, user, password)

if __name__ == '__main__':
    main()