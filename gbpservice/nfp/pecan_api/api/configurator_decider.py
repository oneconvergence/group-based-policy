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


import pecan
class DecideConfigurator(pecan.commands.serve.ServeCommand):
    ''' Custom Commands '''
    arguments = pecan.commands.serve.ServeCommand.arguments + ({
        'name': '--base_with_vm',
        'help': 'an extra command line argument',
        'action': 'store_true',
    },)

    def run(self, args):
        print args.base_with_vm
        setattr(pecan, 'base_with_vm', args.base_with_vm)
        super(DecideConfigurator, self).run(args)

