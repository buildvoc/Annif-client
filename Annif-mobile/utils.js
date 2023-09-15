/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

/* eslint-disable no-var */

(function (window) {
    'use strict';

    window.exifReaderError = function (message) {
        var errorContainer = document.querySelector('.error');
        errorContainer.innerHTML = message;
        errorContainer.classList.remove('hidden');
    };

    window.exifReaderClear = function () {
        var errorContainer;
        var tableBody;
        var thumbnail;
        var tagName, tagDesc;

        errorContainer = document.querySelector('.error');
        errorContainer.classList.add('hidden');
        errorContainer.innerHTML = '';

        tagName = document.getElementsByClassName('tag-name');
        tagName[0].innerHTML = 'Tag name';
        tagName[1].innerHTML = 'Tag name';

        tagDesc = document.getElementsByClassName('tag-description');
        tagDesc[0].innerHTML = 'Tag description';
        tagDesc[1].innerHTML = 'Tag description';

        tableBody = document.getElementsByClassName('exif-table-body');
        tableBody[0].innerHTML = '';
        tableBody[1].innerHTML = '';

        thumbnail = document.getElementById('previewimg');
        thumbnail.classList.add('hidden');
        thumbnail.innerHTML = '';
    };

    window.exifReaderListTags = function (tags) {
        var tableBody;
        var name;
        var description;

        tableBody = document.getElementsByClassName('exif-table-body');
        for (name in tags) {
            description = getDescription(tags[name]);
            if (description !== undefined) {

                [...tableBody].forEach((parent, i) => {
                    const row = document.createElement('tr');
                    row.innerHTML = '<td>' + name + '</td><td>' + description + '</td>';
                    parent.appendChild(row)
                });
            }
        }
    };

    function getDescription(tag) {
        if (Array.isArray(tag)) {
            return tag.map((item) => item.description).join(', ');
        }
        return tag.description;
    }
}(window));