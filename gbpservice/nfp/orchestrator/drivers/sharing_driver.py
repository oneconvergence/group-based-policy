from gbpservice.nfp.orchestrator.drivers import orchestration_driver

class SharingDriver(OrchestrationDriver):
    def select_network_function_device(self, devices, device_data):
        """ Select a NFD which is eligible for sharing

        :param devices: NFDs
        :type devices: list
        :param device_data: NFD data
        :type device_data: dict

        :returns: None -- when device sharing is not supported, or
                          when no device is eligible for sharing
        :return: dict -- NFD which is eligible for sharing

        :raises: exceptions.IncompleteData
        """

        if (
            any(key not in device_data
                for key in ['ports']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model']) or

            type(devices) is not list or

            any(key not in device
                for device in devices
                for key in ['interfaces_in_use'])
        ):
            raise exceptions.IncompleteData()

        token = device_data['token']
        hotplug_ports_count = 1  # for provider interface (default)
        if any(port['port_classification'] == nfp_constants.CONSUMER
               for port in device_data['ports']):
            hotplug_ports_count = 2

        device_service_types_map = (
            self._get_device_service_types_map(token, devices,
                                               network_handler))
        service_type = device_data['service_details']['service_type']
        for device in devices:
            if (
                (device['interfaces_in_use'] + hotplug_ports_count) <=
                self.maximum_interfaces
            ):
                if (service_type.lower() == nfp_constants.VPN.lower() and
                        service_type in device_service_types_map[
                            device['id']]):
                    # Restrict multiple VPN services to share same device
                    # If nfd request service type is VPN and current filtered
                    # device already has VPN service instantiated, ignore this
                    # device and checks for next one
                    continue
                return device
        return None
        
