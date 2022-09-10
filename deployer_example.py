import sys
import os
from rs.utils.basics import Properties
from rs.utils.basics import Logger
from rs.janssen.janssen_lib import ConfigAPIClient


def main():
    local_properties = Properties("./local.properties", "./default.properties")
    logger = Logger(os.path.basename(__file__), local_properties.get("idp_deployment_log_level"), local_properties.get("idp_deployment_log_file"))
    run(logger, local_properties)


def run(logger, local_properties):
    file_name = os.path.basename(__file__)
    logger.debug("Starting {} deployment".format(file_name))
    config_api_client = ConfigAPIClient(logger, local_properties)
    config_api_client.import_attributes("../customization/attributes")
    config_api_client.patch_attributes("../customization/attributes/patch")



if __name__ == "__main__":
    sys.exit(main())
