import time

import requests


def head_request(url, max_requests=10, verbose=False):
    """Get the headers from a url
    Parameters
    ----------
    url : str
        url address for the zip file
    max_requests : int
        number of url download request attempts (default is 10)
    verbose : bool
        boolean indicating if output will be printed to the terminal
        (default is False)
    Returns
    -------
    header : request header object
        request header object for url
    """
    for idx in range(max_requests):
        if verbose:
            msg = f"open request attempt {idx + 1} of {max_requests}"
            print(msg)

        response = requests.head(url, allow_redirects=True)
        if response.status_code != 200:
            if idx < max_requests - 1:
                time.sleep(13)
                continue
            else:
                msg = "Cannot open request from:\n" + f"    {url}\n\n"
                print(msg)
                response.raise_for_status()
        else:
            return response


def get_request(url, timeout=1, max_requests=10, verbose=False):
    """Make a url request
    Parameters
    ----------
    url : str
        url address for the zip file
    verify : bool
        boolean indicating if the url request should be verified
        (default is True)
    timeout : int
        url request time out length (default is 1 seconds)
    max_requests : int
        number of url download request attempts (default is 10)
    verbose : bool
        boolean indicating if output will be printed to the terminal
        (default is False)
    Returns
    -------
    req : request object
        request object for url
    """
    for idx in range(max_requests):
        if verbose:
            msg = f"open request attempt {idx + 1} of {max_requests}"
            print(msg)
        try:
            return requests.get(url, stream=True, timeout=timeout)
        except:
            if idx < max_requests - 1:
                time.sleep(13)
                continue
            else:
                msg = "Cannot open request from:\n" + f"    {url}\n\n"
                print(msg)
                raise requests.HTTPError(msg)
