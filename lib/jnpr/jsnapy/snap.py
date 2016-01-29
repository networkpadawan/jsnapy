from lxml import etree
import os
from jnpr.jsnapy.sqlite_store import JsnapSqlite
import sys
import logging
import colorama
from jnpr.jsnapy import get_path


class Parser:

    def __init__(self):
        self.logger_snap = logging.getLogger(__name__)
        self.log_detail = {'hostname': None}
        colorama.init(autoreset=True)

    def _write_file(self, rpc_reply, format, output_file):
        """
        Writing rpc reply in snap file
        :param rpc_reply: RPC reply
        :param format: xml/text
        :param output_file: name of file
        """
        if isinstance(rpc_reply, bool) and format == "text":
            self.logger_snap.error(
                colorama.Fore.RED +
                "ERROR!! requested node is not present", extra=self.log_detail)
        else:
            err = rpc_reply.xpath("//rpc-error")
            if len(err):
                self.logger_snap.error(
                    colorama.Fore.RED +
                    "\nERROR:",
                    extra=self.log_detail)
                for err_node in err:
                    self.logger_snap.error(
                        err_node.findtext(
                            colorama.Fore.RED +
                            './/error-message'), extra=self.log_detail)
            else:
                with open(output_file, 'w') as f:
                    f.write(etree.tostring(rpc_reply))

    def _check_reply(self, rpc_reply, format):
        """
        Check rpc reply for errors
        :param rpc_reply: RPC reply
        :param format: xml/ text
        :return: return false if reply contains error ow return rpc reply
        """
        if isinstance(rpc_reply, bool) and format == "text":
            self.logger_snap.error(
                colorama.Fore.RED +
                "ERROR!! requested node is not present", extra=self.log_detail)
        else:
            err = rpc_reply.xpath("//rpc-error")
            if len(err):
                self.logger_snap.error(
                    colorama.Fore.RED +
                    "ERROR:",
                    extra=self.log_detail)
                self.logger_snap.error(
                    colorama.Fore.RED +
                    "Complete Error Message: %s" % rpc_reply,
                    extra=self.log_detail)
                for err_node in err:
                    self.logger_snap.error(
                        err_node.findtext(
                            colorama.Fore.RED +
                            './/error-message'), extra=self.log_detail)
            else:
                return etree.tostring(rpc_reply)
        return(False)

    def generate_snap_file(self, output_file, hostname, name, cmd_format):
        """
        This will generate snapshot file name
        :param output_file: either complete file or file tag
        :param name: command or RPC
        :param cmd_format: xml/text
        :return: return output file
        """
        if os.path.isfile(output_file):
            return output_file
        else:
            filename = hostname + '_' + output_file + \
                '_' + name + '.' + cmd_format
            output_file = os.path.join(
                get_path(
                    'DEFAULT',
                    'snapshot_path'),
                filename)
            return output_file

    def store_in_sqlite(
            self, db, hostname, cmd_rpc_name, reply_format, rpc_reply, snap_name):
        """
        Store reply in database
        :param db: database name
        :param hostname: hostname
        :param cmd_rpc_name: Command/RPC
        :param reply_format: xml / text
        :param rpc_reply: RPC reply
        :param snap_name: snap filename
        """
        sqlite_jsnap = JsnapSqlite(hostname, db['db_name'])
        db_dict = dict()
        db_dict['cli_command'] = cmd_rpc_name
        db_dict['snap_name'] = snap_name
        db_dict['filename'] = hostname + '_' + snap_name + \
            '_' + cmd_rpc_name + '.' + reply_format
        db_dict['format'] = reply_format
        db_dict['data'] = self._check_reply(rpc_reply, reply_format)
        sqlite_jsnap.insert_data(db_dict)

    def run_cmd(self, test_file, t, formats, dev, output_file, hostname, db):
        """
        This function takes snapshot for given command and write it in
        snapshot file or database
        """
        command = test_file[t][0].get('command', "unknown command")
        cmd_format = test_file[t][0].get('format', 'xml')
        cmd_format = cmd_format if cmd_format in formats else 'xml'
        self.command_list.append(command)
        cmd_name = '_'.join(command.split())
        try:
            self.logger_snap.info(
                colorama.Fore.BLUE +
                "Taking snapshot for %s ................" %
                command,
                extra=self.log_detail)
            rpc_reply_command = dev.rpc.cli(command, format=cmd_format)
        except Exception:
            self.logger_snap.error(colorama.Fore.RED +
                                   "ERROR occurred %s" %
                                   str(sys.exc_info()[0]), extra=self.log_detail)
            self.logger_snap.error(colorama.Fore.RED +
                                   "\n**********Complete error message***********\n %s" %
                                   str(sys.exc_info()), extra=self.log_detail)
            #raise Exception("Error in command")
            #sys.exc_clear()
            pass
        else:
            snap_file = self.generate_snap_file(
                output_file,
                hostname,
                cmd_name,
                cmd_format)
            self._write_file(rpc_reply_command, cmd_format, snap_file)
            if db['store_in_sqlite'] is True and self._check_reply(
                    rpc_reply_command, cmd_format):
                self.store_in_sqlite(
                    db,
                    hostname,
                    cmd_name,
                    cmd_format,
                    rpc_reply_command,
                    output_file)

    def run_rpc(self, test_file, t, formats, dev, output_file, hostname, db):
        """
        This function takes snapshot for given RPC and write it in
        snapshot file or database
        """
        rpc = test_file[t][0].get('rpc', "unknown rpc")
        self.rpc_list.append(rpc)
        reply_format = test_file[t][0].get('format', 'xml')
        reply_format = reply_format if reply_format in formats else 'xml'
        if len(test_file[t]) >= 2 and 'args' in test_file[t][1]:
            kwargs = {
                k.replace(
                    '-',
                    '_'): v for k,
                v in test_file[t][1]['args'].items()}
            if 'filter_xml' in kwargs:
                from lxml.builder import E
                filter_data = None
                for tag in kwargs['filter_xml'].split('/')[::-1]:
                    filter_data = E(tag) if filter_data is None else E(
                        tag,
                        filter_data)
                    kwargs['filter_xml'] = filter_data
                    print "filter_data"
                    if rpc == 'get-config':
                        self.logger_snap.info(
                            colorama.Fore.BLUE +
                            "Taking snapshot of %s......." %
                            rpc,
                            extra=self.log_detail)
                        rpc_reply = getattr(
                            dev.rpc,
                            rpc.replace(
                                '-',
                                '_'))(
                            options={
                                'format': reply_format},
                            **kwargs)
                    else:
                        self.logger_snap.error(
                            colorama.Fore.RED +
                            "ERROR!!, filtering rpc works only for 'get-config' rpc")
            else:
                try:
                    self.logger_snap.info(
                        colorama.Fore.BLUE +
                        "Taking snapshot of %s......." %
                        rpc,
                        extra=self.log_detail)
                    rpc_reply = getattr(
                        dev.rpc, rpc.replace('-', '_'))({'format': reply_format}, **kwargs)
                except Exception:
                    self.logger_snap.error(colorama.Fore.RED +
                                           "ERROR occurred:\n %s" %
                                           str(sys.exc_info()[0]), extra=self.log_detail)
                    self.logger_snap.error(colorama.Fore.RED +
                                           "\n**********Complete error message***********\n%s" %
                                           str(sys.exc_info()), extra=self.log_detail)
                    return
        else:
            try:
                self.logger_snap.info(
                    colorama.Fore.BLUE +
                    "Taking snapshot of %s............" %
                    rpc,
                    extra=self.log_detail)
                if rpc == 'get-config':
                    rpc_reply = getattr(
                        dev.rpc,
                        rpc.replace(
                            '-',
                            '_'))(
                        options={
                            'format': reply_format})
                else:
                    rpc_reply = getattr(
                        dev.rpc, rpc.replace('-', '_'))({'format': reply_format})
            except Exception:
                self.logger_snap.error(colorama.Fore.RED +
                                       "ERROR occurred: \n%s" %
                                       str(sys.exc_info()[0]), extra=self.log_detail)
                self.logger_snap.error(colorama.Fore.RED +
                                       "\n**********Complete error message***********\n%s" %
                                       str(sys.exc_info()), extra=self.log_detail)
                return

        if 'rpc_reply' in locals():
            snap_file = self.generate_snap_file(
                output_file,
                hostname,
                rpc,
                reply_format)
            self._write_file(rpc_reply, reply_format, snap_file)

        if db['store_in_sqlite'] is True and self._check_reply(
                rpc_reply, reply_format):
            self.store_in_sqlite(
                db,
                hostname,
                rpc,
                reply_format,
                rpc_reply,
                output_file)

    def generate_reply(self, test_file, dev, output_file, hostname, db):
        """
        Analyse test file and call respective functions to generate rpc reply
        for commands and RPC in test file.
        """
        self.command_list = []
        self.rpc_list = []
        self.test_included = []
        formats = ['xml', 'text']
        self.log_detail['hostname'] = hostname

        if 'tests_include' in test_file:
            self.test_included = test_file.get('tests_include')
        else:
            for t in test_file:
                self.test_included.append(t)

        for t in self.test_included:
            if t in test_file:
                if test_file.get(t) is not None and (
                        'command' in test_file[t][0]):
                    #command = test_file[t][0].get('command',"unknown command")
                    self.run_cmd(
                        test_file,
                        t,
                        formats,
                        dev,
                        output_file,
                        hostname,
                        db)
                elif test_file.get(t) is not None and 'rpc' in test_file[t][0]:
                    self.run_rpc(
                        test_file,
                        t,
                        formats,
                        dev,
                        output_file,
                        hostname,
                        db)
                else:
                    self.logger_snap.error(
                        colorama.Fore.RED +
                        "ERROR!!! Test case: '%s' not defined properly" % t, extra=self.log_detail)
            else:
                self.logger_snap.error(
                    colorama.Fore.RED +
                    "ERROR!!! Test case: '%s' not defined !!!!" % t, extra=self.log_detail)