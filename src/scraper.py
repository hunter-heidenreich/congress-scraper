import json
import os
import re
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from tqdm import tqdm


def query_page(
        wd: webdriver.Firefox,
        congress: int = 117,
        bill_type: str = 'house-bill',
        bill_id: int = 1,
        version: str = '',
        cache: bool = True,
        text: bool = False,
):
    """
    Query a page of a bill.

    :param wd: Selenium driver
    :param congress: Congress number (e.g. 117)
    :param bill_type:  Bill type (e.g. 'house-bill', 'senate-bill', 'house-joint-resolution', etc.)
    :param bill_id:  Bill ID (e.g. 1, 2, 3, etc.)
    :param version: Bill version (e.g. '', '/ih', '/rh', etc.)
    :param cache: Whether to cache the page
    :param text: Whether to query the text of the bill
    :return: BS4 object
    """
    t_ = bill_type.replace('-', '_')
    os.makedirs(f'cache/html/{congress}/{t_}', exist_ok=True)

    if text:
        v_ = version.replace('/', '')
        pth = f'cache/html/{congress}/{t_}/{bill_id}-txt{v_}.html'
    else:
        pth = f'cache/html/{congress}/{t_}/{bill_id}-all.html'

    loaded = False
    if cache and os.path.exists(pth):
        with open(pth, 'r') as f:
            html = f.read()
            loaded = True
    else:
        if text:
            url = f'https://www.congress.gov/bill/{congress}th-congress/{bill_type}/{bill_id}/text{version}?format=txt'
        else:
            url = f'https://www.congress.gov/bill/{congress}th-congress/{bill_type}/{bill_id}/all-info'
        wd.get(url)
        html = wd.page_source

        if cache:
            with open(pth, 'w') as f:
                f.write(html)

    return BeautifulSoup(html, 'html.parser'), loaded


def query_bill_text(
        wd: webdriver.Firefox,
        congress: int = 117,
        bill_type: str = 'house-bill',
        bill_id: int = 1,
        version: str = '',
        cache: bool = True,
):
    return query_page(
        wd=wd,
        congress=congress,
        bill_type=bill_type,
        bill_id=bill_id,
        version=version,
        cache=cache,
        text=True,
    )


def query_bill_all_info(
        wd: webdriver.Firefox,
        congress: int = 117,
        bill_type: str = 'house-bill',
        bill_id: int = 1,
        cache: bool = True,
):
    return query_page(
        wd=wd,
        congress=congress,
        bill_type=bill_type,
        bill_id=bill_id,
        version='',
        cache=cache,
        text=False,
    )


def process_bill_overview(
        soup: BeautifulSoup,
):
    out = {}
    for row in soup.find_all("tr"):
        key = row.find_all("th")

        if len(key) == 0:
            continue

        key = key[0].text.strip()[:-1].lower()
        value = row.find_all("td")[0].text.strip()

        if key == 'committees':
            # val_by_chamber = [x.strip() for x in value.split(' | ')]
            # value = []
            # for x in val_by_chamber:
            #     chamber = x.split(' - ')[0][0]  # H or S
            #     value += [y.strip() + f'({chamber})' for y in x.split(' - ')[1].split(';')]
            continue
        elif key == 'latest action' or key == 'latest action (modified)':
            # # 3 things: date, chamber, action
            # v = {
            #     'chamber': 'House' if 'House - ' in value else 'Senate',
            #     'datetime': re.findall(r'\d{2}/\d{2}/\d{4}', value)[0],
            # }
            # v['action'] = value.split(v['datetime'])[1].strip().replace('\xa0\xa0(All Actions)', '')
            # value = v
            continue
        elif key == 'sponsor':
            # 5 things: name, state, district, party, date introduced
            if 'Rep.' in value:
                v = {
                    'name': value.split(' [')[0],  # do we wish to post-process this?
                    'party': value.split(' [')[1].split('-')[0].strip(),
                    'state': value.split(' [')[1].split('-')[1].strip(),
                    'district': value.split(' [')[1].split('-')[2].split(']')[0].strip(),
                    # 'datetime': re.findall(r'\d{2}/\d{2}/\d{4}', value)[0],
                    # 'url': f'https://www.congress.gov{row.find_all("a")[0]["href"]}'
                }
            else:
                v = {
                    'name': value.split(' [')[0],  # do we wish to post-process this?
                    'party': value.split(' [')[1].split('-')[0].strip(),
                    'state': value.split(' [')[1].split('-')[1].strip().split(']')[0].strip(),
                    # 'datetime': re.findall(r'\d{2}/\d{2}/\d{4}', value)[0],
                    # 'url': f'https://www.congress.gov{row.find_all("a")[0]["href"]}'
                }
            value = v
        elif key in {'committee meetings', 'committee reports', 'committee prints'}:
            # v = []
            # for link in row.find_all("a"):
            #     v.append({
            #         'text': link.text.strip(),
            #         'url': link['href'],
            #     })
            # value = v
            continue
        elif key == 'roll call votes':
            # regex get the group matching this on the value r'There have been (\d+) roll call votes'
            match = re.match(r'There have been (\d+) roll call votes', value)
            if match is None:
                value = 0
            else:
                value = int(match.groups()[0])
        else:
            print(f'Unknown key: {key}')
        out[key] = value

    # extract tracker (class=bill_progress)
    progbar = soup.find_all("ol", {"class": "bill_progress"})[0]
    out['tracker'] = [x.text.strip().split('Array')[0] for x in progbar.find_all("li")]

    return out


def process_bill(
        wd: webdriver.Firefox,
        congress: int = 117,
        bill_type: str = 'house-bill',
        bill_id: int = 1,
        sleep_time: float = 3.0
):
    """
    Process a bill.

    :param wd: Selenium driver
    :param congress: Congress number (e.g. 117)
    :param bill_type: Bill type (e.g. 'house-bill', 'senate-bill', 'house-joint-resolution', etc.)
    :param bill_id: Bill ID (e.g. 1, 2, 3, etc.)
    :param sleep_time: Time to sleep between queries
    :return: Whether HTML was loaded from cache
    """

    # Download all HTML data
    soup, from_cache = query_bill_all_info(
        wd=wd,
        congress=congress,
        bill_type=bill_type,
        bill_id=bill_id,
    )

    if not from_cache:
        time.sleep(sleep_time)

    soup_text, from_cache = query_bill_text(
        wd=wd,
        congress=congress,
        bill_type=bill_type,
        bill_id=bill_id,
        version='',  # No version -> current version
    )

    soup_all = soup

    # Initialize output
    short = {
        'house-bill': 'H.R.',
        'senate-bill': 'S.',
        'house-joint-resolution': 'H.J.Res.',
        'senate-joint-resolution': 'S.J.Res.',
        'house-concurrent-resolution': 'H.Con.Res.',
        'senate-concurrent-resolution': 'S.Con.Res.',
        'house-resolution': 'H.Res.',
        'senate-resolution': 'S.Res.',
    }[bill_type]

    out = {
        'id': f'{short}{bill_id}',
        'congress': congress,
        'url': f'https://www.congress.gov/bill/{congress}th-congress/{bill_type}/{bill_id}',
    }

    # Process bill name
    try:
        name = soup.find_all("h1", class_="legDetail")[0].text.strip().split('\n')[0].split(' - ')[1].strip()
        out['title'] = name
    except IndexError:
        print('Failed to find bill name. Assuming it\'s a reserved bill and skipping.')
        return True

    # Process bill overview
    out['overview'] = process_bill_overview(soup.find_all("div", class_="overview")[0])

    # Process titles
    titles_main = soup_all.find_all("div", id="titles_main")[0]

    # short-titles
    try:
        short_titles = titles_main.find_all(
            "div", class_="titles-row")[0].find_all(
            "div", class_="house-column" if 'house' in bill_type else "senate-column"
        )[0].text.strip()
        # sorted(set(
        short_titles = [
            s_.strip()
            for s_ in re.split('\n', short_titles)
            if len(s_) > 0 and 'Short Title' not in s_
        ]  # ))
        out['titles_short'] = '\n'.join(short_titles)
    except IndexError:
        out['titles_short'] = ''

    # official-titles
    official_titles = titles_main.find_all(
        "div", class_="officialTitles")[0].find_all(
        "div", class_="titles-row")[0].find_all(
        "div", class_="house-column" if 'house' in bill_type else "senate-column"
    )[0].text.strip()
    # sorted(set(
    official_titles = [
        s_.strip()
        for s_ in re.split('\n', official_titles)
        if len(s_) > 0 and 'Official Title' not in s_
    ]  # ))
    out['titles_official'] = '\n'.join(official_titles)

    # # Process action list
    # action_list = soup_all.find_all("div", id="allActions-content")[0]
    # actions = []
    # # at minimum: datetime, chamber, action
    # # TODO: full scraping of link, be it to a committee meeting or a vote, etc.
    # ths = []
    # for row in action_list.find_all("tr"):
    #     ths_ = row.find_all("th")
    #     tds = row.find_all("td")
    #     if len(tds) == 0:
    #         ths = ths_
    #         continue
    #     elif len(tds) == 1:
    #         raise Exception('Unknown action format')
    #     elif len(tds) == 2:
    #         v = {
    #             'datetime': tds[0].text.strip(),
    #             'action': {
    #                 'text': tds[1].text.strip(),
    #                 'urls': [x['href'] for x in tds[1].find_all("a")],
    #             }
    #         }
    #
    #         assert ths[0].text.strip() == 'Date' and ths[1].text.strip() == 'All Actions'
    #     elif len(tds) == 3:
    #         v = {
    #             'datetime': tds[0].text.strip(),
    #             'chamber': tds[1].text.strip(),
    #             'action': {
    #                 'text': tds[2].text.strip(),
    #                 'urls': [x['href'] for x in tds[2].find_all("a")],
    #             }
    #         }
    #     else:
    #         raise Exception('Unknown action format')
    #     actions.append(v)
    # out['actions'] = actions

    # Process cosponsors
    out['cosponsors'] = []
    try:
        cosponsors = soup_all.find_all(
            "div", id="cosponsors-content")[0].find_all(
            "table", class_="item_table")[0]

        if cosponsors.find_all('tbody')[0].get('id') != 'withdrawnTbody':
            for row in cosponsors.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) == 0:
                    continue
                elif len(tds) == 2:
                    if 'Rep.' in tds[0].text.strip():
                        v = {
                            'name': tds[0].text.strip().split(' [')[0],  # do we wish to post-process this?
                            'party': tds[0].text.strip().split(' [')[1].split('-')[0].strip(),
                            'state': tds[0].text.strip().split(' [')[1].split('-')[1].strip(),
                            'district': tds[0].text.strip().split(' [')[1].split('-')[2].split(']')[0].strip(),
                            # 'datetime': tds[1].text.strip(),
                            # 'url': f'https://www.congress.gov{row.find_all("a")[0]["href"]}'
                        }
                    else:
                        v = {
                            'name': tds[0].text.strip().split(' [')[0],  # do we wish to post-process this?
                            'party': tds[0].text.strip().split(' [')[1].split('-')[0].strip(),
                            'state': tds[0].text.strip().split(' [')[1].split('-')[1].strip().split(']')[0].strip(),
                            # 'datetime': tds[1].text.strip(),
                            # 'url': f'https://www.congress.gov{row.find_all("a")[0]["href"]}'
                        }
                else:
                    print(tds)
                    raise Exception('Unknown cosponsor format')
                out['cosponsors'].append(v)
    except IndexError:
        pass

    # Process committees
    committees = soup_all.find_all("div", id="committees-content")[0]
    out['committees'] = []
    cur = None
    for row in committees.find_all("tr"):
        ths = row.find_all("th")
        tds = row.find_all("td")
        if len(tds) == 0:
            continue

        try:
            cls = row.get('class')[0]
        except TypeError:
            continue

        if len(ths) == 1 and len(tds) == 3:
            # v = {
            #     'committee': ths[0].text.strip(),
            #     'subcommittee': None,
            #     'datetime': tds[0].text.strip(),
            #     'activity': tds[1].text.strip(),
            #     'related': {
            #         'text': tds[2].text.strip(),
            #         'urls': [x['href'] for x in tds[2].find_all("a")],
            #     }
            # }
            if cls == 'committee':
                v = ths[0].text.strip()
                cur = v
            else:
                # v = cur + '::' + ths[0].text.strip()
                v = ths[0].text.strip()
        elif len(ths) == 0 and len(tds) == 3:
            # v = {
            #     'committee': cur,
            #     'subcommittee': None,
            #     'datetime': tds[0].text.strip(),
            #     'activity': tds[1].text.strip(),
            #     'related': {
            #         'text': tds[2].text.strip(),
            #         'urls': [x['href'] for x in tds[2].find_all("a")],
            #     }
            # }
            v = cur
        elif len(tds) == 4:
            # v = {
            #     'committee': cur,
            #     'subcommittee': tds[0].text.strip(),
            #     'datetime': tds[1].text.strip(),
            #     'activity': tds[2].text.strip(),
            #     'related': {
            #         'text': tds[3].text.strip(),
            #         'urls': [x['href'] for x in tds[3].find_all("a")],
            #     }
            # }
            # v = cur + '::' + tds[0].text.strip()
            v = ths[0].text.strip()
        else:
            raise Exception(f'Unknown committee format. Row headers: {len(ths)} Row values: {len(tds)}')
        out['committees'].append(v)

    # Process related bills
    related_bills = soup_all.find_all("div", id="relatedBills-content")[0]
    out['related_bills'] = []
    for row in related_bills.find_all("tr"):
        # check if class is 'relatedbill_exrow'
        # on bs4 object
        if 'relatedbill_exrow' in row.get('class', ''):
            continue

        tds = row.find_all("td")
        if len(tds) == 0:
            continue
        elif len(tds) == 5:
            v = {
                'bill': tds[0].text.strip(),
                # 'title': tds[1].text.strip(),
                'relationship': tds[2].text.strip(),
                # 'action_latest': {
                #     'datetime': tds[4].text.strip()[:10],
                #     'text': tds[4].text.strip()[10:].strip(),
                # },
                # 'url': f'https://www.congress.gov{row.find_all("a")[0]["href"]}'
            }
        else:
            raise Exception('Unknown related bill format')
        out['related_bills'].append(v)

    # Process subjects
    subjects = soup_all.find_all(
        "div", id="subjects-content")[0]
    sub_nav = subjects.find_all(
        "div", class_="search-column-nav")[0]
    try:
        sub_nav = sub_nav.find_all("ul")[0]
    except IndexError:
        sub_nav = None
    sub_main = subjects.find_all(
        "div", class_="search-column-main")[0].find_all(
        "ul")[0]

    out['policy_areas'] = '' if sub_nav is None else sub_nav.find_all("li")[0].text.strip()
    out['subjects'] = [x.text.strip() for x in sub_main.find_all("li")]

    # # Process summary
    # summary = soup_all.find_all(
    #     "div", id="allSummaries-content")[0]
    # out['summary'] = []
    # for div in summary.find_all("div"):
    #     if 'summarySelector' in div.get('id', ''):
    #         continue
    #
    #     try:
    #         out['summary'].append({
    #             'header': div.find_all("h3")[0].find_all('span')[0].text.strip(),
    #             'text': '\n'.join([p.text.strip() for p in div.find_all("p")]),
    #         })
    #     except IndexError:
    #         continue

    # Process latest summary
    latest_summary = soup_all.find_all(
        "div", id="latestSummary-content")[0]
    out['cur_summary'] = {
        'header': latest_summary.find_all("h3")[0].find_all('span')[0].text.strip(),
        'text': '\n'.join([p.text.strip() for p in latest_summary.find_all("p")]),
    }

    # Process bill text
    out['cur_text'] = {
        'header': soup_text.find_all("h3", class_="currentVersion")[0].find_all('span')[0].text.strip(),
        'text':
            soup_text.find_all("pre", id="billTextContainer")[0].text.split('<DOC>')[1].strip()
            if '<DOC>' in soup_text.find_all("pre", id="billTextContainer")[0].text else
            soup_text.find_all("pre", id="billTextContainer")[0].text.strip(),
    }
    if 'AN ACT\n' in out['cur_text']['text']:
        out['cur_text']['text'] = out['cur_text']['text'].split('AN ACT\n')[1].strip()
    if 'A BILL\n' in out['cur_text']['text']:
        out['cur_text']['text'] = out['cur_text']['text'].split('A BILL\n')[1].strip()

    # # Process bill text revisions
    # out['text'] = []
    # try:
    #     bill_revs = soup_text.find_all("select", id="textVersion")[0].find_all("option")
    #     bill_revs = ['/' + x['value'].split('/')[-1] for x in bill_revs]
    #     for version in bill_revs:
    #         soup_text = query_bill_text(bill_id, version=version)
    #
    #         # Need to check if this version exists or if we get a default to the current version
    #         out['text'].append({
    #             'header': soup_text.find_all("h3", class_="currentVersion")[0].find_all('span')[0].text.strip(),
    #             'body': soup_text.find_all("pre", id="billTextContainer")[0].text.split('<DOC>')[1].strip()
    #             if '<DOC>' in soup_text.find_all("pre", id="billTextContainer")[0].text else
    #             soup_text.find_all("pre", id="billTextContainer")[0].text.strip(),
    #         })
    # except IndexError:
    #     pass

    # Save to disk
    t_ = bill_type.replace(' ', '_')
    pth = f'data/{congress}/{t_}'
    os.makedirs(pth, exist_ok=True)
    with open(f'{pth}/{bill_id}.json', 'w') as f:
        json.dump(out, f, indent=4, sort_keys=True)

    return from_cache


if __name__ == '__main__':
    ix = 1

    # congress = 117
    # btype = 'house-bill'
    # iy = 9709

    # congress = 117
    # btype = 'house-joint-resolution'
    # iy = 106

    # congress = 117
    # btype = 'senate-bill'
    # iy = 5357

    congress = 117
    btype = 'senate-joint-resolution'
    iy = 70

    sleep_time = 5.0

    driver = webdriver.Firefox()

    for ix in tqdm(range(ix, iy + 1)):
        print(f'Bill ID: {ix}')
        if not process_bill(
                driver,
                congress=congress,
                bill_type=btype,
                bill_id=ix,
                sleep_time=sleep_time,
        ):
            time.sleep(sleep_time)

    driver.close()
