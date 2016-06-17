# Copyright 2016 OpenStack Foundation
#
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
#

"""ncp_node_instance_nf_mapping

Revision ID: 54a906e3607a
Revises: 3a22661651c3
Create Date: 2016-06-16 17:05:10.715748

"""

# revision identifiers, used by Alembic.
revision = '54a906e3607a'
down_revision = '3a22661651c3'


from alembic import op
import sqlalchemy as sa


def upgrade(active_plugins=None, options=None):
    op.create_table(
        'ncp_node_instance_network_function_mappings',
        sa.Column('sc_instance_id', sa.String(length=36), nullable=False),
        sa.Column('sc_node_id', sa.String(length=36), nullable=False),
        sa.Column('network_function_id', sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint('sc_instance_id',
                                'sc_node_id',
                                'network_function_id'),
    )


def downgrade(active_plugins=None, options=None):
    pass
