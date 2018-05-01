#!/bin/bash

VERSION=1.0.0
APP=transcode
PACK_DIR=swift-$APP-$VERSION

SCRIPT=$(readlink -f "$0")
BUILDPATH=$(dirname "${SCRIPT}")

CURDIR=$(pwd)

function build_transcode_install_packet() {
    echo "starting build transcode install packet"
    cd ${BUILDPATH}
    rm ${PACK_DIR} -rf
    mkdir -p ${PACK_DIR}/transcode

    cp -rf ffmpeg ${PACK_DIR}/
    cp -rf fonts ${PACK_DIR}/
    cp -rf src/* ${PACK_DIR}/transcode/
    cp -f  install.sh ${PACK_DIR}/

    tar -zcf ${PACK_DIR}.tar.gz ${PACK_DIR}
    cd ${CURDIR}
    echo "transcode install packet builded"
}

echo "----------------------------------------"
build_transcode_install_packet;
sleep 1
echo "----------------------------------------"

