#!/bin/bash

FFMPEG_TARGET_OBJS=/usr/local/sbin/ffmpeg /usr/local/sbin/ffprobe
TRANSCODE_TARGET_DIR=/home/swift/transcode
FONTS_TARGET_DIR=/usr/share/fonts/fonts/zh_CN/TrueType
PM=yum

function rm_fonts() {
    echo "rm ${FONTS_TARGET_DIR} ......"
    rm -rf ${FONTS_TARGET_DIR}
}

function stop_transcode() {
    echo "stop transcode server ......"
    /etc/init.d/transcode stop
}

function rm_ffmpeg() {
    echo "rm ${FFMPEG_DIR} ......"
    rm -rf ${FFMPEG_TARGET_OBJS}
}

function rm_transcode() {
    echo "rm ${TRANSCODE_TARGET_DIR} ......"
    rm -rf ${TRANSCODE_TARGET_DIR}
}

function del_startup() {
    echo "chkconfig --del transcode ......"
    chkconfig --del transcode
    chkconfig transcode off
    rm -rf /etc/rc.d/init.d/transcode
}


echo "uninstall trancode server ......"
stop_transcode;
sleep 2
del_startup;
sleep 1
rm_ffmpeg;
sleep 1
rm_fonts;
sleep 1
rm_transcode
echo "transcode server uninstalled."
