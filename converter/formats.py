#!/usr/bin/env python
# encoding:utf-8

class BaseFormat(object):
    """
    Base format class.

    Supported formats are: ogg, avi, mkv, webm, flv, mov, mp4, mpeg
    """

    format_name = None
    ffmpeg_format_name = None

    def parse_options(self, opt):
        if 'format' not in opt or opt.get('format') != self.format_name:
            raise ValueError('invalid Format format')
        return ['-f', self.ffmpeg_format_name]


class OggFormat(BaseFormat):
    """
    Ogg container format, mostly used with Vorbis and Theora.
    """
    format_name = 'ogg'
    ffmpeg_format_name = 'ogg'


class AviFormat(BaseFormat):
    """
    Avi container format, often used vith DivX video.
    """
    format_name = 'avi'
    ffmpeg_format_name = 'avi'


class MkvFormat(BaseFormat):
    """
    Matroska format, often used with H.264 video.
    """
    format_name = 'mkv'
    ffmpeg_format_name = 'matroska'


class WebmFormat(BaseFormat):
    """
    WebM is Google's variant of Matroska containing only
    VP8 for video and Vorbis for audio content.
    """
    format_name = 'webm'
    ffmpeg_format_name = 'webm'


class FlvFormat(BaseFormat):
    """
    Flash Video container format.
    """
    format_name = 'flv'
    ffmpeg_format_name = 'flv'


class MovFormat(BaseFormat):
    """
    Mov container format, used mostly with H.264 video
    content, often for mobile platforms.
    """
    format_name = 'mov'
    ffmpeg_format_name = 'mov'

    def parse_options(self, opt):
        """
        add -movflags faststart, move moove atom to the file header
        """
        if 'format' not in opt or opt.get('format') != self.format_name:
            raise ValueError('invalid Format format')
        return ['-movflags', 'faststart', '-f', self.ffmpeg_format_name]    


class Mp4Format(BaseFormat):
    """
    Mp4 container format, the default Format for H.264
    video content.
    """
    format_name = 'mp4'
    ffmpeg_format_name = 'mp4'
    
    def parse_options(self, opt):
        """
        add -movflags faststart, move moove atom to the file header
        """
        if 'format' not in opt or opt.get('format') != self.format_name:
            raise ValueError('invalid Format format')
        return ['-movflags', 'faststart', '-f', self.ffmpeg_format_name]   


class MpegFormat(BaseFormat):
    """
    MPEG(TS) container, used mainly for MPEG 1/2 video codecs.
    """
    format_name = 'mpg'
    ffmpeg_format_name = 'mpegts'

    def parse_options(self, opt):
        if 'format' not in opt or opt.get('format') != self.format_name:
            raise ValueError('invalid Format format')
        return ['-f', self.ffmpeg_format_name, '-bsf:v', 'h264_mp4toannexb']


class Mp3Format(BaseFormat):
    """
    Mp3 container, used audio-only mp3 files
    """
    format_name = 'mp3'
    ffmpeg_format_name = 'mp3'


class M3u8Format(BaseFormat):
    """
    hls segment, used mp4/flv segment to hls format
    """
    format_name = 'm3u8'
    ffmpeg_format_name = 'hls'

    def parse_options(self, opt):
        if 'format' not in opt or opt.get('format') != self.format_name:
            raise ValueError('invalid Format format')
        print 'm3u8 segment opts:', opt
        hls = opt.get('hls', None)
        if not hls:
            raise ValueError('invalid m3u8 segment format')
        
        hls_time = hls.get('hls_time', 10)
        hls_list_size = 0
        hls_segment_filename = hls.get('hls_segment_filename', None)

        options = ['-f', self.ffmpeg_format_name]
        options.extend(['-bsf:v', 'h264_mp4toannexb'])
        options.extend(['-hls_time', str(hls_time)])
        options.extend(['-hls_list_size', str(hls_list_size)])
        if hls_segment_filename:
            hls_segment_filename = hls_segment_filename.replace('${count}', '%06d.ts')
            options.extend(['-hls_segment_filename', hls_segment_filename])

        return options


format_list = [
    OggFormat, AviFormat, MkvFormat, WebmFormat, FlvFormat,
    MovFormat, Mp4Format, MpegFormat, Mp3Format, M3u8Format
]
