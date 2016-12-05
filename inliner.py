#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:tabstop=4:expandtab:sw=4:softtabstop=4

import base64
import mimetypes
import re
import urllib
import sys
from bs4 import BeautifulSoup


def is_remote(address):
    return urllib.parse.urlparse(address)[0] in ('http', 'https')


def data_encode_image(name, content):
    return 'data:%s;base64,%s' % (mimetypes.guess_type(name)[0], base64.standard_b64encode(content).decode("utf-8"))


def ignore_url(address):
    url_blacklist = ('getsatisfaction.com',
                     'google-analytics.com',)

    for bli in url_blacklist:
        if address.find(bli) != -1:
            return True

    return False


def get_content(from_, expect_binary=False):
    if is_remote(from_):
        if ignore_url(from_):
            return ''

        with urllib.request.urlopen(from_) as f:
            data = f.read()
        if expect_binary:
            return data
        else:
            return data.decode("utf-8")
    else:
        with open(from_, "rb" if expect_binary else "r") as f:
            return f.read()


def resolve_path(base, target):
    if True:
        return urllib.parse.urljoin(base, target)

    if is_remote(target):
        return target

    if target.startswith('/'):
        if is_remote(base):
            protocol, rest = base.split('://')
            return '%s://%s%s' % (protocol, rest.split('/')[0], target)
        else:
            return target
    else:
        try:
            base, rest = base.rsplit('/', 1)
            return '%s/%s' % (base, target)
        except ValueError:
            return target


def replace_javascript(base_url, soup):
    for js in soup.find_all('script', {'src': re.compile('.+')}):
        try:
            real_js = get_content(resolve_path(base_url, js['src']))
            new_tag = soup.new_tag('script')
            new_tag.string = real_js
            js.replace_with(new_tag)
        except Exception as e:
            print('failed to load javascript from %s' % js['src'])
            print(e)


css_url = re.compile(r'url\((.+)\)')


def replace_css(base_url, soup):
    for css in soup.findAll('link', {'rel': 'stylesheet', 'href': re.compile('.+')}):
        try:
            real_css = get_content(resolve_path(base_url, css['href']))

            def replacer(result):
                try:
                    path = resolve_path(resolve_path(base_url, css['href']), result.groups()[0])
                    return 'url(%s)' % data_encode_image(path, get_content(path, True))
                except Exception as e:
                    print('failed to encode css')
                    print(e)
                    return ''

            new_tag = soup.new_tag('style')
            new_tag.string = re.sub(css_url, replacer, real_css)
            css.replaceWith(new_tag)

        except Exception as e:
            print('failed to load css from %s' % css['href'])
            print(e)


def replace_images(base_url, soup):
    from itertools import chain

    for img in chain(soup.findAll('img', {'src': re.compile('.+')}),
                     soup.findAll('input', {'type': 'image', 'src': re.compile('.+')})):
        try:
            path = resolve_path(base_url, img['src'])
            real_img = get_content(path, True)
            img['src'] = data_encode_image(path.lower(), real_img)
        except Exception as e:
            print('failed to load image from %s' % img['src'])
            print(e)


def replace_backgrounds(base_url, soup):
    for e in soup.find_all(style=lambda x: x and 'background-image' in x):
        new_style = []
        try:
            for property, value in [(p.strip(), v.strip()) for (p, v) in
                                    [x.strip().split(':') for x in e['style'].strip().split(';') if len(x) > 0]]:
                if (property == 'background-image' or property == 'background') and 'url(' in value and not 'url(data' in value:
                    url = value[value.find("(") + 1:value.find(")")]
                    path = resolve_path(base_url, url)
                    img = data_encode_image(path.lower(), get_content(path, True))
                    new_style.append((property, value.replace(url, img)))
                else:
                    new_style.append((property, value))
            e['style'] = '; '.join(property + ': ' + value for property, value in new_style)
        except Exception as e:
            print('failed to load background-image from %s' % e['style'])
            print(e)


def main(url, output_filename):
    soup = BeautifulSoup(get_content(url), 'lxml')

    replace_javascript(url, soup)
    replace_css(url, soup)
    replace_images(url, soup)
    replace_backgrounds(url, soup)

    with open(output_filename, 'wb') as res:
        res.write(str(soup).encode("utf-8"))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
