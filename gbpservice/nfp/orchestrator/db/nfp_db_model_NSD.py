from neutron.db import model_base


class PortInfo(BASE, model_base.HasId, model_base.HasTenant):
    """Represents the Port Information"""
    __tablename__ = 'nfp_port_infos'

    port_model = sa.Column(sa.Enum(nfp_constants.NEUTRON_PORT,
                                   nfp_constants.GBP_PORT,
                                   name='port_model'))
    port_classification = sa.Column(sa.Enum(nfp_constants.PROVIDER,
                                            nfp_constants.CONSUMER,
                                            nfp_constants.MANAGEMENT,
                                            nfp_constants.MONITOR,
                                            nfp_constants.ADVANCE_SHARING,
                                            name='port_classification'))
    port_role = sa.Column(sa.Enum(nfp_constants.ACTIVE_PORT,
                                  nfp_constants.STANDBY_PORT,
                                  nfp_constants.MASTER_PORT,
                                  name='port_role'),
                          nullable=True)



class NetworkFunctionDeviceInterface(BASE, model_base.HasId, model_base.HasTenant):
    """Represents the Network Function Device"""
    __tablename__ = 'nfp_network_function_device_interfaces'

    plugged_in_port_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('nfp_port_infos.id',
                                                 ondelete='SET NULL'),
                                   nullable=True)
    interface_position = sa.Column(sa.Integer(), nullable=False)
    mapped_real_port_id = sa.Column(sa.String(36),
                                    sa.ForeignKey('nfp_port_infos.id',
                                                  ondelete='SET NULL'),
                                    nullable=True)
    network_function_device_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('nfp_network_function_devices.id',
                      ondelete='SET NULL'),
        nullable=False)







