#! /bin/bash

BASE_DIR=$1
DEB_PACKAGE_DIR=$BASE_DIR/deb-packages
version=$2
release=$3
DEBIAN_PATH=$DEB_PACKAGE_DIR/haproxy-agent-$version-$release

print_usage () {

   echo "Usage: "
   echo "       $0 <absolute path of haproxy-agent base directory> <version of package> <release of package>";

}

validate_haproxy_agent_source_dir () {

    if [ "x$BASE_DIR" == "x" ]; then
        echo "Error: haproxy-agent source code directory not specified";
        print_usage;
        exit 0;
    elif [ ! -d $BASE_DIR ]; then
        echo "Error: $BASE_DIR does not exist";
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

create_haproxy_agent_package_dir () {

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
 
    mkdir -p $DEBIAN_PATH/usr/bin
    mkdir -p $DEBIAN_PATH/usr/lib/python2.7/dist-packages/haproxy_agent
}

copy_source_code() {

    cp -r $BASE_DIR/DEBIAN $DEBIAN_PATH/.
    cp -r $BASE_DIR/etc $DEBIAN_PATH/.
    cp -r $BASE_DIR/bin/haproxy_agent $DEBIAN_PATH/usr/bin/.
    cp -r $BASE_DIR/src/* $DEBIAN_PATH/usr/lib/python2.7/dist-packages/haproxy_agent/.

    sed -i "/^Source:/c Source: haproxy-agent-$version-$release" $DEBIAN_PATH/DEBIAN/control
    sed -i "s/^Version:.*/Version: $version-$release/g" $DEBIAN_PATH/DEBIAN/control
    sed -i "/^haproxy-agent/c haproxy-agent ($version-$release)" $DEBIAN_PATH/DEBIAN/changelog

    commit_id=`git log | head -1`
    branch_name=`git rev-parse --abbrev-ref HEAD`
    #echo "Version: $version-$release" > $DEBIAN_PATH/etc/sc-version
    #echo "Branch: $branch_name" >> $DEBIAN_PATH/etc/sc-version
    #echo $commit_id >> $DEBIAN_PATH/etc/sc-version

    chmod 0775 $DEBIAN_PATH/DEBIAN/pre*
    chmod 0775 $DEBIAN_PATH/DEBIAN/post*

}

build_deb_package() {
    
    CURDIR=${PWD}
    cd $DEB_PACKAGE_DIR
    dpkg-deb --build haproxy-agent-$version-$release
    echo "Haproxy Agent package will be available in : $DEB_PACKAGE_DIR/haproxy-agent-$version-$release.deb "
    cd $CURDIR

}

validate_haproxy_agent_source_dir
validate_package_version_release
create_haproxy_agent_package_dir
create_dir_structure
copy_source_code
build_deb_package
