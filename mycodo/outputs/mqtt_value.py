# coding=utf-8
#
# mqtt_value.py - MQTT Output module
#
import copy

from flask_babel import lazy_gettext

from mycodo.databases.models import OutputChannel
from mycodo.outputs.base_output import AbstractOutput
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import add_measurements_influxdb


def constraints_pass_positive_value(mod_input, value):
    """
    Check if the user input is acceptable
    :param mod_input: database object, SQL object with user-saved Output options
    :param value: input value, float or int
    :return: tuple: (bool, list of strings, database object)
    """
    errors = []
    all_passed = True
    if value <= 0:  # Ensure value is positive
        all_passed = False
        errors.append("Must be a positive value")
    return all_passed, errors, mod_input


def constraints_pass_positive_or_zero_value(mod_input, value):
    """
    Check if the user input is acceptable
    :param mod_input: SQL object with user-saved Input options
    :param value: float or int
    :return: tuple: (bool, list of strings)
    """
    errors = []
    all_passed = True
    # Ensure value is positive
    if value < 0:
        all_passed = False
        errors.append("Must be zero or a positive value")
    return all_passed, errors, mod_input


measurements_dict = {
    0: {
        'measurement': 'unitless',
        'unit': 'none'
    }
}

channels_dict = {
    0: {
        'types': ['value'],
        'measurements': [0]
    }
}

OUTPUT_INFORMATION = {
    'output_name_unique': 'MQTT_PAHO_VALUE',
    'output_manufacturer': 'Mycodo',
    'output_name': "MQTT Publish: {}".format(lazy_gettext('Value')),
    'output_library': 'paho-mqtt',
    'measurements_dict': measurements_dict,
    'channels_dict': channels_dict,
    'output_types': ['value'],

    'url_additional': 'http://www.eclipse.org/paho/',

    'interfaces': ['Mycodo'],

    'message': 'An output to publish a value to an MQTT server.',

    'dependencies_module': [
        ('pip-pypi', 'paho', 'paho-mqtt')
    ],

    'options_enabled': [
        'button_send_value'
    ],
    'options_disabled': ['interface'],

    'custom_channel_options': [
        {
            'id': 'hostname',
            'type': 'text',
            'default_value': 'localhost',
            'required': True,
            'name': lazy_gettext('Hostname'),
            'phrase': lazy_gettext('The hostname of the MQTT server')
        },
        {
            'id': 'port',
            'type': 'integer',
            'default_value': 1883,
            'required': True,
            'name': lazy_gettext('Port'),
            'phrase': lazy_gettext('The port of the MQTT server')
        },
        {
            'id': 'topic',
            'type': 'text',
            'default_value': 'paho/test/single',
            'required': True,
            'name': lazy_gettext('Topic'),
            'phrase': lazy_gettext('The topic to publish with')
        },
        {
            'id': 'keepalive',
            'type': 'integer',
            'default_value': 60,
            'required': True,
            'constraints_pass': constraints_pass_positive_or_zero_value,
            'name': lazy_gettext('Keep Alive'),
            'phrase': "{} {}".format(
                lazy_gettext('The keepalive timeout value for the client.'),
                lazy_gettext('Set to 0 to disable.'))
        },
        {
            'id': 'clientid',
            'type': 'text',
            'default_value': 'mycodo_mqtt_client',
            'required': True,
            'name': lazy_gettext('Client ID'),
            'phrase': lazy_gettext('Unique client ID for connecting to the MQTT server')
        },
        {
            'id': 'off_value',
            'type': 'integer',
            'default_value': 0,
            'required': True,
            'name': lazy_gettext('Off Value'),
            'phrase': lazy_gettext('The value to send when an Off command is given')
        }
    ]
}


class OutputModule(AbstractOutput):
    """
    An output support class that operates an output
    """
    def __init__(self, output, testing=False):
        super(OutputModule, self).__init__(output, testing=testing, name=__name__)

        self.publish = None

        output_channels = db_retrieve_table_daemon(
            OutputChannel).filter(OutputChannel.output_id == self.output.unique_id).all()
        self.options_channels = self.setup_custom_channel_options_json(
            OUTPUT_INFORMATION['custom_channel_options'], output_channels)

    def setup_output(self):
        import paho.mqtt.publish as publish

        self.publish = publish

        self.setup_on_off_output(OUTPUT_INFORMATION)
        self.output_setup = True

    def output_switch(self, state, output_type=None, amount=None, output_channel=0):
        measure_dict = copy.deepcopy(measurements_dict)

        try:
            if state == 'on' and amount is not None:
                self.publish.single(
                    self.options_channels['topic'][0],
                    amount,
                    hostname=self.options_channels['hostname'][0],
                    port=self.options_channels['port'][0],
                    client_id=self.options_channels['clientid'][0],
                    keepalive=self.options_channels['keepalive'][0])
                self.output_states[output_channel] = amount
                measure_dict[0]['value'] = amount
            elif state == 'off':
                self.publish.single(
                    self.options_channels['topic'][0],
                    payload=self.options_channels['off_value'][0],
                    hostname=self.options_channels['hostname'][0],
                    port=self.options_channels['port'][0],
                    client_id=self.options_channels['clientid'][0],
                    keepalive=self.options_channels['keepalive'][0])
                self.output_states[output_channel] = False
                measure_dict[0]['value'] = self.options_channels['off_value'][0]
        except Exception as e:
            self.logger.error("State change error: {}".format(e))
            return

        add_measurements_influxdb(self.unique_id, measure_dict)

    def is_on(self, output_channel=0):
        if self.is_setup():
            if output_channel is not None and output_channel in self.output_states:
                return self.output_states[output_channel]
            else:
                return self.output_states

    def is_setup(self):
        return self.output_setup
