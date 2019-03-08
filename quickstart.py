from __future__ import print_function
import json
import requests
import mimetypes
import os
import urllib

SCOPES = ['https://www.googleapis.com/auth/drive']


def get_access_token():
    """
    Gets access token using refresh token and client credentials
    """
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

    token_response = requests.post(url='https://www.googleapis.com/oauth2/v4/token', data=data)

    response_data = token_response.json()
    access_token = response_data['access_token']
    return access_token


def download_file(access_token, file_name, parent_folder_id):
    search_result = search_in_folder(access_token, parent_folder_id, file_name)
    if search_result is None:
        return "File does not exist!"
    else:

        url = 'https://www.googleapis.com/drive/v3/files/' + search_result + '?alt=media'
        params = {
            'Authorization': 'Bearer ' + access_token
        }

        response = requests.get(url=url, headers=params)

        return response.text


def upload_file(access_token, local_path, parent_folder_id):
    file_type = mimetypes.MimeTypes().guess_type(local_path)[0]
    file_to_upload = open(local_path, 'rb')
    file_name = os.path.basename(local_path)
    headers = {
        'Authorization': 'Bearer ' + access_token
    }

    metadata = {
        'name': file_name,
        'parents': [parent_folder_id]
    }

    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
        'file': (file_type, file_to_upload)
    }

    url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsTeamDrives=true'
    response = requests.post(url, headers=headers, files=files)
    return response.json


def create_folder(access_token, name, parent_folder_id):
    url = 'https://www.googleapis.com/drive/v3/files?supportsTeamDrives=true'
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Content-Type': 'application/json'
    }

    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }

    response = requests.post(url, headers=headers, data=json.dumps(metadata))
    return response.json()


def get_children(access_token, folder_id):
    url_params = {
        'supportsTeamDrives': 'true',
        'includeTeamDriveItems': 'true',
        'resource': {'parents': [folder_id]},
        'q': "'{}' in parents and trashed=false".format(folder_id),
        'fields': "nextPageToken, files(id, name, mimeType,modifiedTime), files/parents"
    }
    url = "https://www.googleapis.com/drive/v3/files?{}".format(urllib.parse.urlencode(url_params))

    print(url)
    headers = {
        'Authorization': 'Bearer ' + access_token
    }

    return requests.get(url, headers=headers).text


def search_in_folder(access_token, folder_id, file_name):
    children = json.loads(get_children(access_token, folder_id))['files']
    for child in children:
        if child['name'] == file_name:
            return child['id']
    return None


def search_and_create_folder_path(access_token, path):
    """
    Search and create folders to match given path if needed.
    :param access_token: token needed to access drive
    :param path: path to be created
    :return: last folder id
    """
    path = path.strip('/').split('/')
    current_folder_id = '0AMbf_SZMUMMtUk9PVA'
    search = True
    for i in range(0, len(path)):
        child_to_search = path[i]
        if search is False:
            current_folder_id = create_folder(access_token, child_to_search, current_folder_id)['id']
        else:
            search_result = search_in_folder(
                access_token, current_folder_id, child_to_search
            )
            if search_result is None:
                search = False
                current_folder_id = create_folder(access_token, child_to_search, current_folder_id)['id']
            else:
                current_folder_id = search_result
    return current_folder_id


def search_folder_id(access_token, path):
    """
    Search whether a given path exists, and if it does, return the last folder's id
    :param access_token: access token needed to access drive
    :param path: file path
    :return: last folder's id
    """
    path = path.strip('/').split('/')
    current_folder_id = '0AMbf_SZMUMMtUk9PVA'
    for i in range(0, len(path)):
        child_to_search = path[i]
        search_result = search_in_folder(
            access_token, current_folder_id, child_to_search
        )
        if search_result is None:
            return None
        current_folder_id = search_result
    return current_folder_id


if __name__ == '__main__':
    token = get_access_token()
    # print(get_child_ids('0AMbf_SZMUMMtUk9PVA', token))
    # print(download_file('1aPM-E-g-b3P_WXRwiXWwfMOSDiBXLIg0', token))
    # print(create_folder('testcreatefolder', '1rZFwT0aSX3wko5DYZThmIuPd-9SKlqQA', token))
    # create_path(token, 'testcreatefolder/001/002/003', '19DJjF2cXvj7ZS8gd2MIKvpp_mcSloKqO')
    # print(get_children(token, '0AMbf_SZMUMMtUk9PVA'))
    # print(search_in_folder(token, '0AMbf_SZMUMMtUk9PVA', 'folder800', 'application/vnd.google-apps.folder'))
    # upload_file(token, 'asdf.txt', search_and_create_folder_path(token, 'testcreatefolder/testcreatefolder/123/789'))
    print(download_file(token, 'asdf.txt', search_folder_id(token, 'testcreatefolder/testcreatefolder/123/79')))
