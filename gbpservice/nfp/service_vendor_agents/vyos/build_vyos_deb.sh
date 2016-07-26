#! /bin/bash

#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

set -e

SOURCE_CODE_DIR=$1
DEB_PACKAGE_DIR=$1/deb-packages
version=$2
release=$3
DEBIAN_PATH=$DEB_PACKAGE_DIR/vyos-$version-$release

print_usage () {

   echo "Usage: "
   echo "       $0 <absolute path of vyos-code directory> <version of package> <release of package>";

}

validate_nob_dev_dir () {

    if [ "x$SOURCE_CODE_DIR" == "x" ]; then
        echo "Error: vyos code dir not specified";
        print_usage;
        exit 0;
    elif [ ! -d $SOURCE_CODE_DIR ]; then
        echo "Error: $SOURCE_CODE_DIR does not exist";
        print_usage;
        exit 0;
    fi;
}

validate_package_version_release () {

    if [ "x$version" == "x" ]; then
        echo "Error: Package version not specified";
        print_usage;
        exit 0;
    elif [ "x$release" == "x" ]; then
        echo "Error: Package release not specified";
        print_usage;
        exit 0;
    fi

}

create_deb_package_dir () {

    if [ -d $DEB_PACKAGE_DIR ]; then
        :
    else 
        mkdir -p $DEB_PACKAGE_DIR
    fi

}

create_dir_structure () {

    # creating base directory for package
    if [ -d $DEBIAN_PATH ] ; then
       rm -rf $DEBIAN_PATH/*   
    else
       mkdir -p $DEBIAN_PATH
    fi 

    mkdir -p $DEBIAN_PATH/config/auth
    mkdir -p $DEBIAN_PATH/usr/bin
    mkdir -p $DEBIAN_PATH/usr/share
    mkdir -p $DEBIAN_PATH/etc/network/
    mkdir -p $DEBIAN_PATH/config/scripts
    mkdir -p $DEBIAN_PATH/etc/dhcp3/dhclient-exit-hooks.d/
}


copy_source_code () {

    commit_id=`git log | head -1`
    branch_name=`git rev-parse --abbrev-ref HEAD`
    echo "Version: $version-$release" > $DEBIAN_PATH/etc/sc-version

    cp -r $SOURCE_CODE_DIR/DEBIAN $DEBIAN_PATH/.
    cp -r $SOURCE_CODE_DIR/etc $DEBIAN_PATH/.

    cp -r $SOURCE_CODE_DIR/bin/vyos $DEBIAN_PATH/usr/bin/.
    cp -r $SOURCE_CODE_DIR/src $DEBIAN_PATH/usr/share/vyos

    cp -r $SOURCE_CODE_DIR/src/vyos-pbr/interfaces $DEBIAN_PATH/etc/network/.
    cp -r $SOURCE_CODE_DIR/src/vyos-pbr/interface-post-up $DEBIAN_PATH/etc/network/.
    cp -r $SOURCE_CODE_DIR/src/vyos-pbr/management_pbr $DEBIAN_PATH/etc/dhcp3/dhclient-exit-hooks.d/.

    # TODO: Do we need this
    cp -r $SOURCE_CODE_DIR/src/vyos_init_script/restart_vpn $DEBIAN_PATH/config/scripts/.
    mv $DEBIAN_PATH/usr/share/vyos/vyos-pbr $DEBIAN_PATH/usr/share/
    sed -i "s/vyos ([0-9]*.[0-9]*-*[0-9]*)/vyos ($version-$release)/g" $DEBIAN_PATH/DEBIAN/changelog    
    sed -i "/^Source:/c Source: vyos-$version-$release" $DEBIAN_PATH/DEBIAN/control
    sed -i "s/^Version:.*/Version: $version-$release/g" $DEBIAN_PATH/DEBIAN/control
}

build_deb_package () {

    CURDIR=${PWD}
    cd $DEB_PACKAGE_DIR
    dpkg-deb --build vyos-$version-$release
    cd $CURDIR

    echo "Vyos package will be available in : $DEB_PACKAGE_DIR/vyos-$version-$release.deb "
}



validate_nob_dev_dir
validate_package_version_release
create_deb_package_dir
create_dir_structure
copy_source_code
build_deb_package

