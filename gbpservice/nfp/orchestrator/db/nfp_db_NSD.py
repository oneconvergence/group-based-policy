from gbpservice.nfp.orchestrator.db import NFPDbBase



class NFPDbBaseNSD(NFPDbBase):
    def __init__(self, *args, **kwargs):
        super(NFPDbBaseNSD, self).__init__(*args, **kwargs)

    def _set_plugged_in_port_for_nfd_interface(self, session, nfd_interface_db,
                                               interface, is_update=False):
        plugged_in_port_id = interface.get('plugged_in_port_id')
        if not plugged_in_port_id:
            if not is_update:
                nfd_interface_db.plugged_in_port_id = None
            return
        with session.begin(subtransactions=True):
            port_info_db = nfp_db_model.PortInfo(
                id=plugged_in_port_id['id'],
                port_model=plugged_in_port_id['port_model'],
                port_classification=plugged_in_port_id['port_classification'],
                port_role=plugged_in_port_id['port_role'])
            if is_update:
                session.merge(port_info_db)
            else:
                session.add(port_info_db)
            session.flush()
            nfd_interface_db.plugged_in_port_id = port_info_db['id']
            del interface['plugged_in_port_id']


    def create_network_function_device_interface(self, session,
                                                 nfd_interface):
        with session.begin(subtransactions=True):
            mapped_real_port_id = nfd_interface.get('mapped_real_port_id')
            nfd_interface_db = nfp_db_model.NetworkFunctionDeviceInterface(
                id=(nfd_interface.get('id') or uuidutils.generate_uuid()),
                tenant_id=nfd_interface['tenant_id'],
                interface_position=nfd_interface['interface_position'],
                mapped_real_port_id=mapped_real_port_id,
                network_function_device_id=(
                    nfd_interface['network_function_device_id']))
            self._set_plugged_in_port_for_nfd_interface(
                session, nfd_interface_db, nfd_interface)
            session.add(nfd_interface_db)

            return self._make_network_function_device_interface_dict(
                nfd_interface_db)

    def update_network_function_device_interface(self, session,
                                                 nfd_interface_id,
                                                 updated_nfd_interface):
        with session.begin(subtransactions=True):
            nfd_interface_db = self._get_network_function_device_interface(
                session, nfd_interface_id)
            self._set_plugged_in_port_for_nfd_interface(
                session, nfd_interface_db, updated_nfd_interface,
                is_update=True)
            nfd_interface_db.update(updated_nfd_interface)
            return self._make_network_function_device_interface_dict(
                nfd_interface_db)

    def delete_network_function_device_interface(
            self, session, network_function_device_interface_id):
        with session.begin(subtransactions=True):
            network_function_device_interface_db = (
                self._get_network_function_device_interface(
                    session, network_function_device_interface_id))
            if network_function_device_interface_db.plugged_in_port_id:
                self.delete_port_info(
                    session,
                    network_function_device_interface_db.plugged_in_port_id)
            session.delete(network_function_device_interface_db)

    def _get_network_function_device_interface(self, session,
                                               network_function_device_id):
        try:
            return self._get_by_id(
                session,
                nfp_db_model.NetworkFunctionDeviceInterface,
                network_function_device_id)
        except exc.NoResultFound:
            raise nfp_exc.NetworkFunctionDeviceNotFound(
                network_function_device_id=network_function_device_id)

    def get_network_function_device_interface(
            self, session, network_function_device_interface_id,
            fields=None):
        network_function_device_interface = (
            self._get_network_function_device_interface(
                session, network_function_device_interface_id))
        return self._make_network_function_device_interface_dict(
            network_function_device_interface, fields)

    def get_network_function_device_interfaces(self, session, filters=None,
                                               fields=None, sorts=None,
                                               limit=None, marker=None,
                                               page_reverse=False):
        marker_obj = self._get_marker_obj(
            'network_function_device_interfaces', limit, marker)
        return self._get_collection(
            session,
            nfp_db_model.NetworkFunctionDeviceInterface,
            self._make_network_function_device_interface_dict,
            filters=filters, fields=fields,
            sorts=sorts, limit=limit,
            marker_obj=marker_obj,
            page_reverse=page_reverse)


    def _make_network_function_device_interface_dict(self, nfd_interface,
                                                     fields=None):
        res = {'id': nfd_interface['id'],
               'tenant_id': nfd_interface['tenant_id'],
               'plugged_in_port_id': nfd_interface['plugged_in_port_id'],
               'interface_position': nfd_interface['interface_position'],
               'mapped_real_port_id': nfd_interface['mapped_real_port_id'],
               'network_function_device_id': (
                   nfd_interface['network_function_device_id']),
               }
        return res





