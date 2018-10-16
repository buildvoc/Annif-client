#!/usr/bin/env python3
"""Module for accessing Annif REST API in a Pythonic way"""

import requests

# Default API base URL
API_BASE = 'http://dev.annif.org/v1/'


class AnnifClient:
    """Client class for accessing Annif REST API in a Pythonic way"""

    def __init__(self, api_base=API_BASE):
        self.api_base = api_base

    @property
    def projects(self):
        """Get a list of projects available on the API endpoint"""
        req = requests.get(self.api_base + 'projects')
        return req.json()['projects']

    def get_project(self, project_id):
        """Get a single project by project ID"""
        req = requests.get(self.api_base + 'projects/{}'.format(project_id))
        return req.json()

    def analyze(self, project_id, text, limit=None, threshold=None):
        """Analyze text (either a string or a file-like object) using a specified
        project and optional limit and/or threshold settings."""
        if not isinstance(text, str):
            text = text.read()

        payload = {'text': text}

        if limit is not None:
            payload['limit'] = limit

        if threshold is not None:
            payload['threshold'] = threshold

        url = self.api_base + 'projects/{}/analyze'.format(project_id)
        req = requests.post(url, data=payload)
        return req.json()['results']

    def __str__(self):
        """Return a string representation of this object"""
        return "AnnifClient(api_base='{}')".format(self.api_base)


if __name__ == '__main__':
    print("Demonstrating usage of AnnifClient")

    print()

    print("* Creating an AnnifClient object")
    annif = AnnifClient()
    print("Now we have an AnnifClient object:", annif)
    print()
    print("* Finding the available projects")
    for project in annif.projects:
        print("Project id: {:<16} lang: {}  name: {}".format(
            project['project_id'], project['language'], project['name']))

    print()

    print("* Looking up information about a specific project")
    project = annif.get_project('yso-en')
    print("Project id: {:<16} lang: {}  name: {}".format(
        project['project_id'], project['language'], project['name']))

    print()

    print("* Analyzing a short text from a string")
    results = annif.analyze(project_id='yso-en',
                            text='The quick brown fox jumped over the lazy dog')
    for result in results:
        print("<{}>\t{:.4f}\t{}".format(
            result['uri'], result['score'], result['label']))

    print()

    print("* Analyzing a longer text from a file, with a limit on number of results")
    with open('LICENSE') as license_file:
        results = annif.analyze(project_id='yso-en',
                                text=license_file, limit=5)
        for result in results:
            print("<{}>\t{:.4f}\t{}".format(
                result['uri'], result['score'], result['label']))
