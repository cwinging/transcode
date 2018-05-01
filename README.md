# Python Video Converter

基于ffmpeg命令行的转码服务。

提供RESTful转码接口，参考了七牛转码接口参数
    
    {
        "scope" : "a/b/c/d/1.mp4",
        "targetTemplate" : "${filename}_${Resolution}_${vb}.${subffix}",
        "domain" : "http://www.ebook.com",
        "taskID": "",
        "rootDir" : "",
        "deadline" : 0,
        "callbackUrl" : "",
        "callbackBody" : "",
        "callbackBodyType" : "",
        "persistentOps" : "avthumb/mp4/acodec/aac/ab/128k/ar/44100/vcodec/h264/s/360x240/aspect/3:2/r/25",
        "persistentNotifyUrl" : "http://www.abc.com/transcode/notify",
        "persistentPipeline" : "",
        "persistentNotifyBody" : "",
        "persistentNotifyType" : "",
        "fsize" : -1,
        "checksum" : ""
    }    


## Quickstart

###转码系统组件：

    转码系统由客户端，转码任务队列，转码服务，转码作业管理组成。
    流程如下：
    1.客户端向转码任务队列发送转码任务。
    2.转码任务队列排队转码任务，接受任务请求，并按照FIFO原则派发任务。
    3.转码服务向队列请求转码任务，开始执行转码任务，并上报转码结果给作业管理系统。
    4.作业管理系统接收转码上报，写入数据库，提供转码作业信息的查询。


![image](http://jitrtc.com/download/transcode.png)


###转码任务队列

队列基于httpmq([https://github.com/hnlq715/httpmq](https://github.com/hnlq715/httpmq "httpmq"))实现，支持put/get操作。

    1.put操作
    基于http get方式：http://host:port/?name=your_queue_name&opt=put&data=url_encoded_text_message&auth=mypass123

    基于http post方式：
    http://host:port/?name=your_queue_name&opt=put&auth=mypass123
    ...data...

    2.get操作
    http://host:port/?charset=utf-8&name=your_queue_name&opt=get&auth=mypass123

###转码任务描述

    转码任务采用json格式，格式如下：

    {
        "scope" : "a/b/c/d/1.mp4",
        "targetTemplate" : "${filename}_${Resolution}_${vb}.${subffix}",
        "domain" : "http://www.ebook.com",
        "taskID": "",
        "rootDir" : "",
        "deadline" : 0,
        "callbackUrl" : "",
        "callbackBody" : "",
        "callbackBodyType" : "",
        "persistentOps" : "avthumb/mp4/acodec/aac/ab/128k/ar/44100/vcodec/h264/s/360x240/aspect/3:2/r/25",
        "persistentNotifyUrl" : "http://www.abc.com/transcode/notify",
        "persistentPipeline" : "",
        "persistentNotifyBody" : "",
        "persistentNotifyType" : "",
        "fsize" : -1,
        "checksum" : ""
    }    


## Plan
基于分片的分布式转码服务 ....

## Documentation and tests
   
test目录下有给转码队列发送http json例子，读者可以根据自己需求自定义转码persistentOps


## Installation and requirements

     1.python setup.py install
     2.python server/transcode_server.py -c server/transcode.cfg


## Authors and Copyright

Copyright &copy; 2015-2016. cwinging@163.com. 

## Licensing and Patents

Although FFmpeg is licensed under LGPL/GPL, Python Video Converter only invokes the
existing ffmpeg executables on the system (ie. doesn’t link to the ffmpeg
libraries), so it doesn’t need to be LGPL/GPL as well.

The same applies to patents. If you’re in a country which recognizes software
patents, it’s up to you to ensure you’re complying with the patent laws. Please
read the FFMpeg Legal FAQ for more information.
