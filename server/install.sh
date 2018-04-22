#!/bin/bash

SCRIPT=$(readlink -f "$0")
INSTALLPATH=$(dirname "${SCRIPT}")
FFMPEG_DIR=${INSTALLPATH}/ffmpeg
TRANSCODE_DIR=${INSTALLPATH}/transcode
HTTPMQ_DIR=${INSTALLPATH}/httpmq
FONTS_DIR=${INSTALLPATH}/fonts
TRANSCODE_TARGET_DIR=/home/swift/transcode
FONTS_TARGET_DIR=/usr/share/fonts/fonts/zh_CN/TrueType
HTTPMQ_TARGET_DIR=/home/swift/httpmq
PM=yum

function welcome () {
    echo "-----------------------------------------------------------------"
    echo "This script will guide you to install your transcode server."
    echo "Press [ENTER] to continue"
    echo "-----------------------------------------------------------------"
    read dummy
    echo
}


function ffmpeg_install() {
    echo "-----------------------------------------------------------------"
    echo "starting ffmpeg install"
    cp -rf ${FFMPEG_DIR}/bin/* /usr/local/sbin
    chmod a+x /usr/local/sbin/ffmpeg
    chmod a+x /usr/local/sbin/ffprobe
    cp -rf ${FFMPEG_DIR}/lib/libiconv.so.2.5.1 /usr/local/lib
    ln -s /usr/local/lib/libiconv.so.2.5.1 /usr/local/lib/libiconv.so.2
    ln -s /usr/local/lib/libiconv.so.2.5.1 /usr/local/lib/libiconv.so
    echo "/usr/local/lib" >> /etc/ld.so.conf.d/ffmpeg.conf
    ldconfig
    echo "ffmpeg installed"
    echo "-----------------------------------------------------------------"
}


function transcode_install() {
    echo "-----------------------------------------------------------------"
    echo "starting transcoding server install"
    CURDIR=`pwd`
    cd ${TRANSCODE_DIR}
    python setup.py install
    mkdir -p ${TRANSCODE_TARGET_DIR}
    cp -rf server/* ${TRANSCODE_TARGET_DIR}
    cd ${CURDIR}
    echo "transcoding server installed"
    echo "-----------------------------------------------------------------"
}

function fonts_install() {
    echo "-----------------------------------------------------------------"
    echo "starting zh_CN fonts install"
    mkdir -p ${FONTS_TARGET_DIR}
    cp -rf ${FONTS_DIR}/* ${FONTS_TARGET_DIR}
    CURDIR=`pwd`
    cd ${FONTS_TARGET_DIR}
    mkfontscale
    mkfontdir
    fc-cache -fv
    cd ${CURDIR}
    echo "fonts installed"
    echo "-----------------------------------------------------------------"
}


function StartUp() {
    init_name=$1
    echo "Add ${init_name} service at system startup..."
    if [ "$PM" = "yum" ]; then
        chkconfig --add ${init_name}
        chkconfig ${init_name} on
    elif [ "$PM" = "apt" ]; then
        update-rc.d -f ${init_name} defaults
    fi
}


function transcode_self_starting() {
    echo "-----------------------------------------------------------------"
    echo "starting transcode self starting install"
    cp -f ${INSTALLPATH}/transcode/server/transcode /etc/rc.d/init.d/
    chmod a+x /etc/rc.d/init.d/transcode
    StartUp transcode
    echo "transcode self starting installed"
    echo "-----------------------------------------------------------------"
}

welcome;
fonts_install;
sleep 2
ffmpeg_install;
sleep 2
transcode_install;
sleep 2
transcode_self_starting