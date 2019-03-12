from __future__ import print_function
import json
import requests
import mimetypes
import os
import urllib
import time
import math
import shelve
from time import sleep
import errno
SCOPES = ['https://www.googleapis.com/auth/drive']
token_expiration_time = math.inf
access_token = ""


def get_access_token():
    """
    Gets access token using refresh token and client credentials. When an unexpired access token already exists, return
    that one.
    """
    global access_token
    global token_expiration_time
    if access_token != "" and token_expiration_time > time.time() + 100:
        return access_token

    with open('credentials.json') as f:
        creds_data = json.load(f)
    client_id = creds_data['credentials']['clientId']
    refresh_token = creds_data['credentials']['refreshToken']
    client_secret = creds_data['credentials']['clientSecret']

    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }

    try:
        r = requests.post(url='https://www.googleapis.com/oauth2/v4/token', data=data)
        r.raise_for_status()
        response_data = r.json()
        access_token = response_data['access_token']
        token_expiration_time = response_data['expires_in'] + time.time()
        return access_token
    except requests.exceptions.HTTPError as e:
        print(e)
    except requests.exceptions.RequestException as e:
        print(e)


def download_by_path(path):
    """
    Download a file by specified path in drive. Save it to the same location in current directory
    :param path:
    :return: nothing
    """
    search_result = search_by_path(path)
    if search_result is not None:
        url_params = {
            'alt': 'media'
        }

        headers = {
            'Authorization': 'Bearer ' + get_access_token()
        }

        url = 'https://www.googleapis.com/drive/v3/files/' + search_result + '?{}'.format(
            urllib.parse.urlencode(url_params))

        try:
            r = requests.get(url=url, headers=headers)
            if not os.path.exists(os.path.dirname(path)):
                try:
                    os.makedirs(os.path.dirname(path))
                except OSError as exc:  # Guard against race condition
                    if exc.errno != errno.EEXIST:
                        raise

            with open(path, "wb") as f:
                f.write(r.content)
        except requests.exceptions.ConnectionError:
            print('Connection error')
            sleep(5)
            return download_by_path(path)
        except requests.exceptions.RequestException as e:
            print('Downloading file failed')
            print(e)
    else:
        print("File not found")


def upload_by_path(local_path, target_path, create_path):
    """
    Upload a file from local dir to target dir on drive.
    :param local_path: file location on disk
    :param target_path: target path for drive
    :param create_path: boolean, if set to true creates the required path on drive.
    :return: fileId of uploaded file
    """
    if create_path is True:
        search_result = search_and_create_folder_path(target_path)
    else:
        search_result = search_by_path(target_path)
    if search_result is not None:
        file_type = mimetypes.MimeTypes().guess_type(local_path)[0]
        file_to_upload = open(local_path, 'rb')
        file_name = os.path.basename(local_path)

        url_params = {
            'uploadType': 'multipart',
            'supportsTeamDrives': 'true'

        }

        headers = {
            'Authorization': 'Bearer ' + get_access_token()
        }

        metadata = {
            'name': file_name,
            'parents': [search_result]
        }

        files = {
            'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
            'file': (file_type, file_to_upload)
        }

        url = 'https://www.googleapis.com/upload/drive/v3/files?{}'.format(urllib.parse.urlencode(url_params))
        try:
            r = requests.post(url, headers=headers, files=files)
            return r.json()
        except requests.exceptions.ConnectionError:
            print('Connection error')
            sleep(5)
            return upload_by_path(local_path, search_result, create_path)
        except requests.exceptions.RequestException as e:
            print('Uploading file ' + '"' + file_name + '" failed')
            print(e)
    else:
        print("Upload path not found")


def create_folder(name, parent_folder_id):
    """
    Create a folder in specified parent folder.
    :param name: folder name
    :param parent_folder_id: parent folder id
    :return: fileId of created folder
    """
    url_params = {
        'supportsTeamDrives': 'true',
        'fields': 'id'
    }

    headers = {
        'Authorization': 'Bearer ' + get_access_token(),
        'Content-Type': 'application/json'
    }

    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',

        'parents': [parent_folder_id]
    }

    url = 'https://www.googleapis.com/drive/v3/files?{}'.format(urllib.parse.urlencode(url_params))
    try:
        r = requests.post(url, headers=headers, data=json.dumps(metadata))
        return r.json()
    except requests.exceptions.ConnectionError:
        print('Connection error')
        sleep(5)
        return create_folder(name, parent_folder_id)
    except requests.exceptions.RequestException as e:
        print('Creating folder ' + '"' + name + '" failed')
        print(e)


def get_children(folder_id):
    """
    Get all children of specified folder. Calls get_children_next_page if nextPageToken is populated
    :param folder_id: fileId of the folder
    :return: JSON data of the children
    """
    url_params = {

        'supportsTeamDrives': 'true',
        'includeTeamDriveItems': 'true',
        'resource': {'parents': [folder_id]},
        'q': "'{}' in parents and trashed=false".format(folder_id),
        'fields': "nextPageToken, files(id, name, mimeType,modifiedTime), files/parents",
    }

    headers = {
        'Authorization': 'Bearer ' + get_access_token()
    }

    url = "https://www.googleapis.com/drive/v3/files?{}".format(urllib.parse.urlencode(url_params))
    try:
        r = requests.get(url, headers=headers)
        if 'nextPageToken' in r.json():
            return get_children_next_page(r.json(), folder_id, r.json()['nextPageToken'])
        return r.json()
    except requests.exceptions.ConnectionError:
        print('Connection error')
        sleep(5)
        return get_children(folder_id)
    except requests.exceptions.RequestException as e:
        print('Getting children failed')
        print(e)


def get_children_next_page(prev_results, folder_id, page_token):
    """
    Get children on next page of results. Works the same way as get_children, except appends children data to existing
    data and calls itself when nextPageToken is populated
    :param prev_results: results from the previous page
    :param folder_id: fileId of the parent folder
    :param page_token: nextPageToken
    :return: children with next page of results added to them
    """
    url_params = {
        'supportsTeamDrives': 'true',
        'includeTeamDriveItems': 'true',
        'resource': {'parents': [folder_id]},
        'q': "'{}' in parents and trashed=false".format(folder_id),
        'fields': "nextPageToken, files(id, name, mimeType,modifiedTime), files/parents",
        'pageToken': page_token
    }

    headers = {
        'Authorization': 'Bearer ' + get_access_token()
    }

    url = "https://www.googleapis.com/drive/v3/files?{}".format(urllib.parse.urlencode(url_params))
    try:
        r = requests.get(url, headers=headers)
        prev_results['files'].extend(r.json()['files'])
        if 'nextPageToken' in r.json():
            return get_children_next_page(prev_results, folder_id, r.json()['nextPageToken'])
        return prev_results
    except requests.exceptions.ConnectionError:
        print('Connection error')
        sleep(5)
        return get_children_next_page(prev_results, folder_id, page_token)
    except requests.exceptions.RequestException as e:
        print('Getting children failed')


def search_in_folder(folder_id, file_name):
    """
    Search a file in folder. Calls get children and loops through them to find specified file name
    :param folder_id: parent folder id
    :param file_name: file (or folder) name to search
    :return: if found, the child id, None otherwise
    """
    print('called search for ' + file_name)
    children = get_children(folder_id)['files']
    for child in children:
        if child['name'] == file_name:
            return child['id']
    return None


def search_and_create_folder_path(path):
    """
    Search and create folders to match given path if needed. Also checks cache for previously searched folder paths, if
    path not in cache then continues with the search and adds result to cache
    :param path: path to be created
    :return: last folder id
    """
    path = path.strip('/').split('/')
    current_folder_id = '0AMbf_SZMUMMtUk9PVA'
    search = True

    for i in range(0, len(path)):
        fullpath = '/'.join(path[:i + 1])
        child_to_search = path[i]

        # if folder was created in previous loop, no point in searching something from there, just create a new folder
        if search is False:
            current_folder_id = create_folder(child_to_search, current_folder_id)['id']
            write_to_cache(fullpath, current_folder_id)
        else:
            check = check_cache(fullpath)
            # didn't find anything from cache
            if check is None:
                search_result = search_in_folder(current_folder_id, child_to_search)
                # didn't find requested folder in current folder, create a new one
                if search_result is None:
                    search = False
                    current_folder_id = create_folder(child_to_search, current_folder_id)['id']
                # found requested folder, set its id to current folder id
                else:
                    current_folder_id = search_result
                # write results to cache
                write_to_cache(fullpath, current_folder_id)
            # found required path from cache, just set its id for current folder id
            else:
                current_folder_id = check
    return current_folder_id


def search_by_path(path):
    """
    Search whether a given path exists, and if it does, return the last folder's id
    :param path: file path
    :return: last folder's id
    """
    path = path.strip('/').split('/')
    current_folder_id = '0AMbf_SZMUMMtUk9PVA'
    for i in range(0, len(path)):
        fullpath = '/'.join(path[:i + 1])
        check = check_cache(fullpath)
        child_to_search = path[i]
        if check is None:
            search_result = search_in_folder(current_folder_id, child_to_search)
            if search_result is None:
                return None
            current_folder_id = search_result
            write_to_cache(fullpath, current_folder_id)
        else:
            current_folder_id = check
    return current_folder_id


def write_to_cache(path, value):
    """ Write path: id to cache """
    with shelve.open('cache') as cache:
        cache[path] = value


def check_cache(path):
    """ Check cache for specified key """
    with shelve.open('cache') as cache:
        if path in cache:
            return cache[path]
        return None


if __name__ == '__main__':
    # download_folder_id = search_by_path('000/100/110')
    # download_file('abc.txt', download_folder_id)
    # print(download_by_path('000/400/420/421/1/asdf.txt'))
    print(download_by_path('000/400/420/421/240/ab.txt'))
