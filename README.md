# Python Video Converter

基于ffmpeg命令行的转码服务。

提供REstful转码接口，参考了七牛转码接口参数
    
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

    from converter import Converter
    c = Converter()

    info = c.probe('test1.ogg')

    conv = c.convert('test1.ogg', '/tmp/output.mkv', {
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
        }})

    for timecode in conv:
        print "Converting (%f) ...\r" % timecode


## Plan
基于分片的分布式转码服务 ....

## Documentation and tests
   
test目录下有给转码接口发送http json例子，读者可以根据自己需求自定义转码persistentOps


## Installation and requirements

To install the package:

    python setup.py install

Note that this only installs the Python Video Converter library. The `ffmpeg`
and `ffprobe` tools should be installed on the system separately, with all the
codec and format support you require.

If you need to compile and install the tools manually, have a look at the
example script `test/install-ffmpeg.sh` (used for automated test suite). It may
or may not be useful for your requirements, so don't just blindly run it -
check that it does what you need first.

## Authors and Copyright

Copyright &copy; 2015-2016. cwinging@163.com. 

## Licensing and Patents

Although FFmpeg is licensed under LGPL/GPL, Python Video Converter only invokes the
existing ffmpeg executables on the system (ie. doesn’t link to the ffmpeg
libraries), so it doesn’t need to be LGPL/GPL as well.

The same applies to patents. If you’re in a country which recognizes software
patents, it’s up to you to ensure you’re complying with the patent laws. Please
read the FFMpeg Legal FAQ for more information.
