# coding: utf-8

"""SteelConnection

Convienience objects for making REST API calls
to Riverbed SteelConnect Manager.

Usage:
    sc = steelconnection.SConnect(scm_name, username, password)

    Optional keyword api_version can be used to specify an API version number.
    Currently there is only one API version: '1.0'.

    Once you have instantiated an object as shown above,
    you can use the object to make calls to the REST API.

    For example, to get all nodes in the realm:
    nodes = sc.config.get('nodes')
    ... or in a specifc org:
    nodes = sc.config.get('/org/' + orgid + '/nodes')

    Any call that does not result in a success (HTTP status code 200)
    will raise an exception, so calls should be wrapped in a try/except pair.
"""

from __future__ import print_function
import json
import sys
import warnings

import requests

from .__version__ import __version__
from .exceptions import AuthenticationError, APINotEnabled
from .exceptions import BadRequest, ResourceGone, InvalidResource
from .image_download import _download_image
from .lookup import _LookUp
from .input_tools import get_input, get_username, get_password_once
from . import auth


ASCII_ART = r"""
   ______          _______                       __  _
  / __/ /____ ___ / / ___/__  ___  ___  ___ ____/ /_(_)__  ___
 _\ \/ __/ -_) -_) / /__/ _ \/ _ \/ _ \/ -_) __/ __/ / _ \/ _ \
/___/\__/\__/\__/_/\___/\___/_//_/_//_/\__/\__/\__/_/\___/_//_/
"""

BINARY_DATA_MESSAGE = (
    "Binary data returned. "
    "Use '.savefile(filename)' method or access using '.response.content'."
)


class SConnect(object):
    r"""Make REST API calls to Riverbed SteelConnect Manager.

    Args:
        realm (str): (optional) FQDN of SteelConnect Manager.
        username (str): (optional) Admin account name.
        password (str): (optional) Admin account password.
        use_netrc (bool): (optional) Get credentials from .netrc file.
        api_version (str): (optional) REST API version.
        proxies (dict): (optional) Dictionary of proxy servers.
        on_error (str): (optional) Define behavior for failed requests.
        timeout (float or tuple): (optional)
            As a float: The number of seconds to wait for the server
                        to send data before giving up
            or a :ref:`(connect timeout, read timeout) <timeouts>` tuple.
        connection_attempts (str): (optional) Number of login attemps.

    Attributes:
        realm (str): FQDN of SteelConnect Manager.
        api_version (str): SteelConnect Manager REST API version.
        ascii_art (str): Project logo.
        timeout (float or tuple): Timeout values for requests.
        result: Contains last result returned from a request.
        response: Response object from last request.
        session: Request session object used to access REST API.
    """

    def __init__(
        self,
        realm=None,
        username=None,
        password=None,
        use_netrc=False,
        api_version='1.0',
        proxies=None,
        on_error='raise',
        timeout=(5, 60),
        connection_attempts=3,
    ):
        r"""Initialize a new steelconnection object."""
        self.__scm_version = None
        self.__version__ = __version__
        self.api_version = api_version
        self.ascii_art = ASCII_ART
        self.timeout = timeout
        self.result = None
        self.response = None
        self.lookup = _LookUp(self)
        self.session = requests.Session()
        self.session.proxies = proxies if proxies else self.session.proxies
        self.session.headers.update({'Accept': 'application/json'})
        self.session.headers.update({'Content-type': 'application/json'})

        self.realm = realm
        if use_netrc:
            # requests will look for .netrc if auth is not provided.
            if not realm:
                raise ValueError('Must supply realm when using .netrc.')
            if username or password:
                error = 'Do not supply username or password when using .netrc.'
                raise ValueError(error)
        elif realm and username and password:
            self.session.auth = username, password
        else:
            self.realm = auth.get_realm(self, realm, connection_attempts)
            creds = auth.get_creds(
                self, username, password, connection_attempts,
            )
            self.session.auth = creds
        # replace exception handler after auth completes.
        self._raise_exception = self._exception_handling(on_error)

    # Primary methods:

    def get(self, resource, params=None, api='scm.config'):
        r"""Send a GET request to the SteelConnect.Config API.

        :param str resource: api resource to get.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        self.response = self._request(
            request_method=self.session.get,
            url=self.make_url(api, resource),
            params=params,
        )
        self.result = self._get_result(self.response)
        if self.result is None:
            self._raise_exception(self.response)
        return self.result

    def getstatus(self, resource, params=None):
        r"""Send a GET request to the SteelConnect.Reporting API.

        :param str resource: api resource to get.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        return self.get(resource, params, api='scm.reporting')

    def delete(self, resource, data=None, params=None, api='scm.config'):
        r"""Send a DELETE request to the SteelConnect.Config API.

        :param str resource: api resource to get.
        :param dict data: (optional) Dictionary of 'body' data to be sent.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        self.response = self._request(
            request_method=self.session.delete,
            url=self.make_url(api, resource),
            params=params,
            data=data,
        )
        self.result = self._get_result(self.response)
        if self.result is None:
            self._raise_exception(self.response)
        return self.result

    def post(self, resource, data=None, api='scm.config'):
        r"""Send a POST request to the SteelConnect.Config API.

        :param str resource: api resource to get.
        :param dict data: (optional) Dictionary of 'body' data to be sent.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        self.response = self._request(
            request_method=self.session.post,
            url=self.make_url(api, resource),
            data=data,
        )
        self.result = self._get_result(self.response)
        if self.result is None:
            self._raise_exception(self.response)
        return self.result

    def put(self, resource, data=None, params=None, api='scm.config'):
        r"""Send a PUT request to the SteelConnect.Config API.

        :param str resource: api resource to get.
        :param dict data: (optional) Dictionary of 'body' data to be sent.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        self.response = self._request(
            request_method=self.session.put,
            url=self.make_url(api, resource),
            params=params,
            data=data,
        )
        self.result = self._get_result(self.response)
        if self.result is None:
            self._raise_exception(self.response)
        return self.result

    def stream(self, resource, params=None, api='scm.config'):
        r"""Send a GET request with streaming binary data.

        :param str resource: api resource to get.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: dict, or list
        """
        self.response = self.session.get(
            url=self.make_url(api, resource),
            params=params,
            stream=True,
        )
        for chunk in self.response.iter_content(chunk_size=65536):
            yield chunk

    # These do the heavy lifting.

    def make_url(self, api, resource):
        r"""Combine attributes and resource as a url string.

        :param str api: api route, usually 'scm.config' or 'scm.reporting'.
        :param str resource: resource path.
        :returns: Complete URL path to access resource.
        :rtype: str
        """
        resource = resource[1:] if resource.startswith('/') else resource
        return 'https://{}/api/{}/{}/{}'.format(
            self.realm, api, self.api_version, resource,
        )

    def _request(self, request_method, url, data=None, params=None):
        r"""Send a request using the specified method.

        :param request_method: requests.session verb.
        :param str url: complete url and path.
        :param dict data: (optional) Dictionary of 'body' data to be sent.
        :param dict params: (optional) Dictionary of query parameters.
        :returns: Dictionary or List of Dictionaries based on request.
        :rtype: object
        """
        data = json.dumps(data) if data and isinstance(data, dict) else data
        response = request_method(
            url=url, params=params, data=data, timeout=self.timeout,
        )
        return response

    def _get_result(self, response):
        r"""Return response data as native Python datatype.

        :param requests.response response: Response from HTTP request.
        :returns: Dictionary or List of Dictionaries based on response.
        :rtype: dict, list, or None
        """
        if not response.ok:
            if response.text and 'Queued' in response.text:
                # work-around for get:'/node/{node_id}/image_status'
                return response.json()
            else:
                return None
        if response.headers['Content-Type'] == 'application/octet-stream':
            return {'status': BINARY_DATA_MESSAGE}
        if not response.json():
            return {}
        elif 'items' in response.json():
            return response.json()['items']
        else:
            return response.json()

    # These handle binary content.

    def download_image(self, nodeid, save_as=None, build=None, quiet=False):
        r"""Download image and save to file.
        :param str nodeid: The node id of the appliance.
        :param str save_as: The file path to download the image.
        :param str build: Target hypervisor for image.
        :param bool quiet: Disable update printing when true.
        """
        return _download_image(
            sconnect=self,
            nodeid=nodeid,
            save_as=save_as,
            build=build,
            quiet=quiet,
        )

    def savefile(self, filename):
        r"""Save binary return data to a file.

        :param str filename: Where to save the response.content.
        """
        with open(filename, 'wb') as fd:
            fd.write(self.response.content)

    # Property methods that appear like dynamic attributes.

    @property
    def scm_version(self):
        """Return version and build number of SteelConnect Manager.

        :returns: SteelConnect Manager version and build number.
        :rtype: str
        """
        if self.__scm_version is None:
            try:
                info = self.get('info', api='common')
                self.__scm_version = '{sw_version}_{sw_build}'.format(**info)
            except (InvalidResource, KeyError):
                self.__scm_version = 'unavailable'
            else:
                if not info.get('scm_id'):
                    self.__scm_version = 'Not a SteelConnect Manager'
        return self.__scm_version

    @property
    def sent(self):
        """Return summary of the previous API request.

        :returns: Details regarding previous API request.
        :rtype: str
        """
        return '{}: {}\nData Sent: {}'.format(
            self.response.request.method,
            self.response.request.url,
            repr(self.response.request.body),
        )

    @property
    def received(self):
        """Return summary of the previous API response.

        :returns: Details regarding previous API request.
        :rtype: str
        """
        error_message = None
        if not self.response.ok and self.response.text:
            try:
                details = self.response.json()
                error_message = details.get('error', {}).get('message')
            except ValueError:
                pass
        return 'Status: {} - {}\nError: {}'.format(
            self.response.status_code,
            self.response.reason,
            repr(error_message),
        )

    # Error handling and Exception generation.

    def _exception_handling(self, on_error):
        choices = {
            'raise': self._on_error_raise_exception,
            'exit': self._on_error_exit,
        }
        return choices.get(on_error, self._on_error_do_nothing)

    def _on_error_raise_exception(self, response):
        r"""Return an appropriate exception if required.

        :param requests.response response: Response from HTTP request.
        :returns: Exception if non-200 response code else None.
        :rtype: BaseException, or None
        """
        exceptions = {
            400: BadRequest,
            401: AuthenticationError,
            404: InvalidResource,
            410: ResourceGone,
            502: APINotEnabled,
        }
        if not response.ok:
            exception = exceptions.get(response.status_code, RuntimeError)
            raise exception('\n'.join((self.received, self.sent)))

    def _on_error_exit(self, response):
        r"""Display error and exit.

        :param requests.response response: Response from HTTP request.
        :returns: None.
        :rtype: None
        """
        display = '\n'.join((self.received, self.sent))
        if not response.ok:
            print(display, file=sys.stderr)
            sys.exit(1)

    def _on_error_do_nothing(self, response):
        r"""Return None to short-circuit the exception process.

        :param requests.response response: Response from HTTP request.
        :returns: None.
        :rtype: None
        """
        return None

    # Gratuitous __dunder__ methods.

    def __bool__(self):
        """Return the success of the last request in Python3.

        :returns: True of False if last request succeeded.
        :rtype: bool
        """
        return False if self.response is None else self.response.ok

    def __nonzero__(self):
        """Return the success of the last request in Python2.

        :returns: True of False if last request succeeded.
        :rtype: bool
        """
        return self.__bool__()

    def __repr__(self):
        """Return a string consisting of class name, realm, and api.

        :returns: Information about this object.
        :rtype: str
        """
        scm_version = self.scm_version if self.scm_version else 'unavailable'
        details = ', '.join([
            "realm: '{}'".format(self.realm),
            "scm version: '{}'".format(scm_version),
            "api version: '{}'".format(self.api_version),
            "package version: '{}'".format(self.__version__),
        ])
        return '{}({})'.format(self.__class__.__name__, details)

    def __str__(self):
        """Return a string with information about this object instance.

        :returns: Information about this object.
        :rtype: str
        """
        scm_version = self.scm_version if self.scm_version else 'unavailable'
        details = [
            'SteelConnection:',
            "realm: '{}'".format(self.realm),
            "scm version: '{}'".format(scm_version),
            "api version: '{}'".format(self.api_version),
            "package version: '{}'".format(self.__version__),
        ]
        details.extend(self.sent.splitlines())
        details.extend(self.received.splitlines())
        return '\n>> '.join(details)


# Deprecated classes.

def SConAPI(*args, **kwargs):
    warnings.simplefilter('always', DeprecationWarning)  # Disable filter.
    warnings.warn(
        "'SConAPI' is deprecated, "
        "use steelconnection.SConnect() instead",
        category=DeprecationWarning,
        stacklevel=2
    )
    warnings.simplefilter('default', DeprecationWarning)  # Reset filter.
    return SConnect(*args, **kwargs)


def SConWithoutExceptions(*args, **kwargs):
    warnings.simplefilter('always', DeprecationWarning)  # Disable filter.
    warnings.warn(
        "'SConWithoutExceptions' is deprecated, "
        "use steelconnection.SConnect(on_error=None) instead",
        category=DeprecationWarning,
        stacklevel=2
    )
    warnings.simplefilter('default', DeprecationWarning)  # Reset filter.
    return SConnect(*args, on_error=None, **kwargs)


def SConExitOnError(*args, **kwargs):
    warnings.simplefilter('always', DeprecationWarning)  # Disable filter.
    warnings.warn(
        "'SConExitOnError' is deprecated, "
        "use steelconnection.SConnect(on_error=None) instead",
        category=DeprecationWarning,
        stacklevel=2
    )
    warnings.simplefilter('default', DeprecationWarning)  # Reset filter.
    return SConnect(*args, on_error='exit', **kwargs)
