TOP_DIR=$2
NFP_SCRIPTS_DIR=$1
ConfiguratorQcow2Image=$3
VyosQcow2Image=$4
sudo bash $NFP_SCRIPTS_DIR/configure_nfp_gbp_params.sh $NFP_SCRIPTS_DIR $TOP_DIR  
 
sudo bash $NFP_SCRIPTS_DIR/wakeup_service.sh $ConfiguratorQcow2Image $VyosQcow2Image $NFP_SCRIPTS_DIR $TOP_DIR 

