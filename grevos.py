#!/usr/bin/env python
"""GREVOS -  generate combined activity graphs any number of GitHub repositories.

https://github.com/pferrot/grevos
"""
import json
import argparse
import re
import csv
import datetime
import os.path
import hashlib
import copy

from requests import get
from jinja2 import Environment, FileSystemLoader

#######################################################################
# Global variables.

# Need to be manually updated. Should allow to prevent using old JSON cache
# when the schema has been modified with a new version.
m_schema_version = 3
m_cache_folder = 'cache'
m_output_folder = 'output'
m_csv_date_format = "%m/%d/%Y %H:%M:%S"
m_email_to_author_file = None
m_email_to_author = {}
m_name_to_author_file = None
m_name_to_author = {}
m_unknown_username = "<unknown>"
m_commits_to_ignore_separator = "-"
m_now = datetime.datetime.now()
m_epoch = datetime.datetime.utcfromtimestamp(0)
# OTHERS is used when only top contributors are displayed. In that case,
# we still want to display how much the rest of the contributors contributed.
m_others_username = "OTHERS"
m_total_username = "TOTAL"

#######################################################################
# All methods defined first. See entry point at the end of the file.

def str2bool(v):
    """Return the Boolean value corresponding to a String.

    'yes', 'true', 't', 'y', '1' (case insensitive) will return True.
    'no', 'false', 'f', 'n', '0' (case insensitive) will return false.
    Any other value will raise a argparse.ArgumentTypeError.
    """
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def unix_time_millis(dt):
    """Return the UNIX Epoch time of a given datetime.
    """
    return (dt - m_epoch).total_seconds() * 1000

def get_commit_details(scheme, host, base_path, owner, repo, commit_sha, git_token):
    """Return the details of a given commit SHA, as a JSON object.

    Example:
    {
        "stats" : {
            "additions" : 23,
            "deletions" : 12,
            "total"     : 35,
            "difference": 11
        },
        "date": W2011-04-14T16:00:49Z"
    }

    Return None in case the GitHub API returns anything else than a 200 status code.
    """
    url = "%s%s%s/repos/%s/%s/commits/%s" % (scheme, host, base_path, owner, repo, commit_sha)
    #print (url)
    headers = \
        {
         'Authorization': 'token %s' % git_token
        }
    reply = get(url, headers=headers)
    status_code = reply.status_code
    if status_code == 200:
        out = reply.content
        js = json.loads(out.decode('utf-8'))

        if args.ignore_files and "files" in js:
            for f in js["files"]:
                if "filename" in f and f["filename"] in args.ignore_files and "status" in f and f["status"] == "added":
                    print ("    Ignoring commit %s because file '%s' was added" % (commit_sha, f["filename"]))
                    return {}

        #print (json.dumps(js, indent=4, sort_keys=True))
        commit_date = None
        if "commit" in js and "author" in js["commit"] and "date" in js["commit"]["author"]:
            commit_date = js["commit"]["author"]["date"]
        else:
            print ("    Could not find commit date in \n\n%s" % json.dumps(js, indent=4, sort_keys=True))

        result = {}
        result["stats"] = js["stats"]
        # Let track the difference as it may be what is most meaningful to measure.
        result["stats"]["difference"] = result["stats"]["additions"] - result["stats"]["deletions"]
        result["date"] = commit_date
        return result
    else:
        print ("    Erreur retrieving commit (status code: %d) at %s" % (status_code, url))
        return None

def remove_commits_to_ignore(r, min_commit_difference, max_commit_difference, commits_to_ignore):
    """Removes commits listed in commits_to_ignore or those with too many lines added/removed from a given result set and returns it.

    min_commit_difference in an integer. Commits with a 'difference' value greater than that value are removed.
    max_commit_difference is an integer. Commits with a 'difference' value lower than that value are removed.
    commits_to_ignore is a list of commits SHA. Commits with a 'sha' contained in that list are removed.

    If min_commit_difference in None, then no check is done on the minimum value of the 'difference' metric.
    If max_commit_difference in None, then no check is done on the maximum value of the 'difference' metric.
    If commits_to_ignore is None, then no check is done on the value of the 'sha' of the commit.
    """
    if r and len(r.keys()) > 0:
        print("Removing commits to ignore")
        to_remove_authors = []
        for k in r.keys():
            author_data = r[k]
            to_remove_indexes = []
            for idx, x  in enumerate(author_data):
                if "stats" in x and "difference" in x["stats"] and max_commit_difference != None and x["stats"]["difference"] > max_commit_difference:
                    print("    Removing commit because it is above the max difference limit in %s/%s: %s (%d)" % (x["owner"], x["repo"], x["sha"], x["stats"]["difference"]))
                    to_remove_indexes.append(idx)
                elif "stats" in x and "difference" in x["stats"] and min_commit_difference != None and x["stats"]["difference"] < min_commit_difference :
                    print("    Removing commit because it is below the min difference limit in %s/%s: %s (%d)" % (x["owner"], x["repo"], x["sha"], x["stats"]["difference"]))
                    to_remove_indexes.append(idx)
                elif commits_to_ignore and len(commits_to_ignore) > 0 and "sha" in x and x["sha"] in commits_to_ignore:
                    print("    Removing commit to ignore in %s/%s: %s" % (x["owner"], x["repo"], x["sha"]))
                    to_remove_indexes.append(idx)
            for idx in reversed(to_remove_indexes):
                del author_data[idx]
            # If an author does not have any commit left, he must be removed.
            if len(r[k]) == 0:
                to_remove_authors.append(k)
        for author in to_remove_authors:
            if author in r:
                r.pop(author)
    return r

def populate_totals(the_list):
    """Adds a 'total_stats_author' object to every item in the_list.

    the_list is a list of JSON objects, sorted chronologically, each JSON representing a commit
    made by a given author. All items in the list belong to the same author.

    Example item before processing:
    {
        "sha": "6b9b8c59703560f197c71adfe0ac9770cfeffb33",
        "date": "2011-04-14T16:00:49Z",
        "date_unix": "1302796849000.0",
        "author": "jdoe",
        "author_name": "John Doe",
        "author_email": "jdoe@testmail.com",
        "owner": "MyOrg",
        "repo": "MyRepo",
        "branch": "master",
        "stats" : {
            "additions" : 23,
            "deletions" : 12,
            "total"     : 35,
            "difference": 11
        }
    }

    After processing:
    {
        "sha": "6b9b8c59703560f197c71adfe0ac9770cfeffb33",
        "date": "2011-04-14T16:00:49Z",
        "date_unix": "1302796849000.0",
        "author": "jdoe",
        "author_name": "John Doe",
        "author_email": "jdoe@testmail.com",
        "owner": "MyOrg",
        "repo": "MyRepo",
        "branch": "master",
        "stats" : {
            "additions" : 23,
            "deletions" : 12,
            "total"     : 35,
            "difference": 11
        },
        "total_stats_author" : {
            "nb_commits": 12
            "additions" : 734,
            "deletions" : 423,
            "total"     : 1157,
            "difference": 311
        },
    }

    where 'total_stats_author' shows the sum of all items in the list until the
    current item (inclusive). So in the example above, the item is the 12th item
    in the list (since nb_commits == 12).
    """
    if the_list:
        previous = None
        for one_item in the_list:
            total_stats_author = {}
            if not previous:
                total_stats_author["nb_commits"] = 1
                total_stats_author["additions"] = one_item["stats"]["additions"]
                total_stats_author["deletions"] = one_item["stats"]["deletions"]
                total_stats_author["difference"] = one_item["stats"]["difference"]
                total_stats_author["total"] = one_item["stats"]["total"]
            else:
                total_stats_author["nb_commits"] = previous["total_stats_author"]["nb_commits"] + 1
                total_stats_author["additions"] = previous["total_stats_author"]["additions"] + one_item["stats"]["additions"]
                total_stats_author["deletions"] = previous["total_stats_author"]["deletions"] + one_item["stats"]["deletions"]
                total_stats_author["difference"] = previous["total_stats_author"]["difference"] + one_item["stats"]["difference"]
                total_stats_author["total"] = previous["total_stats_author"]["total"] + one_item["stats"]["total"]
            one_item["total_stats_author"] = total_stats_author
            previous = one_item
        return the_list
    else:
        return the_list

def get_csv_output_filename(source_file_full_path):
    """Returns the filename of the generated CSV file.
    """
    return get_output_filename(source_file_full_path, "csv")

def get_html_output_filename(source_file_full_path):
    """Returns the filename of the generated HTML file.
    """
    return get_output_filename(source_file_full_path, "html")

def get_output_filename(source_file_full_path, extension):
    """Returns the filename of a generated file file with the given extension.
    """
    base_name = os.path.basename(source_file_full_path)
    if base_name.find('.') > 0:
        base_name = base_name[:base_name.find('.')]
    return '%s_%s.%s' % (base_name, m_now.strftime("%Y%m%d%H%M%S"), extension)

def get_html_title(source_file_full_path):
    """Returns the title to be used in the generated HTML file.

    The title is the source filename without extension, with '_' characters
    replaced by whitespaces and all uppercase.
    """
    base_name = os.path.basename(source_file_full_path)
    if base_name.find('.') > 0:
        base_name = base_name[:base_name.find('.')]
    return base_name.replace('_', ' ').replace('-', ' ').upper()

def get_csv_output_filename_with_path(source_file_full_path):
    """Returns the filename with path of the generated CSV file.

    The path is specified by the end user (default: 'output').
    """
    return get_filename_with_path(get_csv_output_filename(source_file_full_path), m_output_folder)

def get_html_output_filename_with_path(source_file_full_path):
    """Returns the filename with path of the generated HTML file.

    The path is specified by the end user (default: 'output').
    """
    return get_filename_with_path(get_html_output_filename(source_file_full_path), m_output_folder)

def get_filename_with_path(filename, folder):
    """Returns the filename with path, given the base filename and folder.
    """
    return "%s%s%s" % (folder, "" if folder.endswith("/") else "/", filename)

def get_cache_filename(url):
    """Returns the filename of the cache file for a given URL.

    The cache filename is the SHA1 of the GitHub URL used to retrieve the date, the files to be ignored
    (although that feature is currently hidden/disabled) and the schema version.

    Using a so called schema version allows to easily modify the data stored in the cache in future versions
    as legacy cache files be ignored (because a different schema version will lead to a different
    SHA1, i.e. different filename). This comes at the cost of having the fetch the data from GitHub again.
    """
    # Important to take args.ignore_files into account as the result depends on this parameter.
    cache_filename = hashlib.sha1(("%s%s%d" % (url, ",".join(args.ignore_files) if args.ignore_files else "", m_schema_version)).encode('utf-8')).hexdigest()
    #print("Cache filename: %s" % cache_filename)
    return cache_filename

def get_cache_filename_with_path(url):
    """Returns the filename (with full path) of the cache file for a given url.

    See get_cache_filename(url) for more details.
    """
    return get_filename_with_path(get_cache_filename(url), m_cache_folder)

def cache(url, the_json):
    """Saves the given JSON in a local cache file (overwrites it if it exists already).
    """
    #print ("    Caching: %s" % url)
    with open(get_cache_filename_with_path(url), 'w') as outfile:
        json.dump(the_json, outfile)


def get_cache(url):
    """Returns the cache for a given URL.

    The resuls is a tuple (JSON, highest_date, sha, nb_commits) where highest_date is the
    date of the most recent commit in the JSON and sha the SHA for that most recent commit.

    Returns None if no cache file exists.

    If an error occurs when reading the file, a message is logged and None is returned.
    """
    cache_file = get_cache_filename_with_path(url)
    if not os.path.exists(cache_file):
        print("    No cache (file does not exist: %s)" % cache_file)
        return None
    else:
        print("    Cache found (file: %s)" % cache_file)
        try:
            with open(cache_file) as json_data:
                d = json.load(json_data)
                merged_results = merge_sort_results(d)
                nb_commits = len(merged_results)
                highest_date = None
                sha = None
                if merged_results and len(merged_results) > 0:
                    highest_date = merged_results[len(merged_results) - 1]["date"]
                    sha = merged_results[len(merged_results) - 1]["sha"]

                #print ("Found cache, date: %s\n\n%s" % (highest_date, json.dumps(d, indent=4, sort_keys=True)))
                return (d, highest_date, sha, nb_commits)
        except:
            print("    Error loading cache from file %s, so ignoring file" % cache_file)
            return None


def get_rep_stats(scheme, host, base_path, owner, repo, branch, since, git_token, index_repo, total_nb_repos):
    """Returns a dictionary where the keys are the authors and the values a list of their commits
    for a given repo defined by its scheme, host, base_path, owner and repo.

    git_token is a valid GitHub API token wth read access to the repository.
    index_repo and total_nb_repos and simply specified to log progress information.

    Simple example result with one single commit:
    {
        "jdoe": [
            {
                "sha": "6b9b8c59703560f197c71adfe0ac9770cfeffb33",
                "date": "2011-04-14T16:00:49Z",
                "date_unix": "1302796849000.0",
                "author": "jdoe",
                "author_name": "John Doe",
                "author_email": "jdoe@testmail.com",
                "owner": "MyOrg",
                "repo": "MyRepo",
                "branch": "master",
                "stats" : {
                    "additions" : 23,
                    "deletions" : 12,
                    "total"     : 35,
                    "difference": 11
                },
                "total_stats_author" : {
                    "nb_commits": 12
                    "additions" : 734,
                    "deletions" : 423,
                    "total"     : 1157,
                    "difference": 311
                },
            }
        ]
    }

    Note that results are cached for future reuse. The cache will be udpated with new
    commits everytime the method is called.
    """
    next_url = "%s%s%s/repos/%s/%s/commits?sha=%s%s" % (scheme, host, base_path, owner, repo, branch, "&since=%s" % since if since else "")
    cache_url = next_url
    print ("Processing: %s (%s)" % (next_url, "repo %d / %d" % (index_repo, total_nb_repos)))

    since_date = None
    # The 'original_since_date' is what the user specified, whereas the 'since_date'
    # might be the once recovered from the cache, see below.
    original_since_date = None
    if since:
        since_date = datetime.datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ")
        original_since_date = since_date

    counter = 0
    nb_cache = 0
    result = {}

    from_cache = get_cache(cache_url)
    cache_sha = None
    # We found something in cache and there is a date.
    if from_cache and from_cache[1]:
        cache_date = from_cache[1]
        since_date = datetime.datetime.strptime(cache_date, "%Y-%m-%dT%H:%M:%SZ")
        #print("    Cache date: %s" % cache_date)
        next_url = "%s%s%s/repos/%s/%s/commits?sha=%s%s" % (scheme, host, base_path, owner, repo, branch, "&since=%s" % cache_date if cache_date else "")
        result = from_cache[0]
        cache_sha = from_cache[2]
        counter = from_cache[3]
        nb_cache = counter
        print("    Recovered %d commits from cache" % counter)

    while next_url:
        headers = \
            {
             'Authorization': 'token %s' % git_token
            }
        reply = get(next_url, headers=headers)
        status_code = reply.status_code
        if status_code == 200:
            next_url = None
            headers = reply.headers
            if "Link" in headers and 'rel="next"' in headers['Link']:
                #print(headers['Link'])
                headers_list = headers['Link'].split(",")
                for h in headers_list:
                    if 'rel="next"' in h:
                        m = re.search('<(.+?)>', h)
                        if m:
                            next_url = m.group(1)
                            #print ("Next URL: %s" % next_url)

            #print ("Headers: %s" % headers)
            out = reply.content
            js = json.loads(out.decode('utf-8'))
            #print (json.dumps(js, indent=4, sort_keys=True))

            for one_js in js:

                author_email = None
                commit_sha = None
                author_login = None
                #print (json.dumps(one_js, indent=4, sort_keys=True))
                if "author" in one_js and one_js["author"] and "login" in one_js["author"]:
                    author_login = one_js["author"]["login"]
                if "sha" in one_js:
                    commit_sha = one_js["sha"]
                    # Since we query 'since' the highest date from the cache, we should get the highest result
                    # from the cache in the response. So lets ignore it so that it is not duplicated.
                    if cache_sha and commit_sha == cache_sha:
                        #print("    Ignoring SHA from cache: %s" % cache_sha)
                        continue

                one_result = {}


                author_email = None
                author_name = None
                if "commit" in one_js and "author" in one_js["commit"] and "email" in one_js["commit"]["author"] and one_js["commit"]["author"]["email"]:
                    author_email = one_js["commit"]["author"]["email"]
                if "commit" in one_js and "author" in one_js["commit"] and "name" in one_js["commit"]["author"] and one_js["commit"]["author"]["name"]:
                    author_name = one_js["commit"]["author"]["name"]

                #else:
                #    print ("Author: %s" % author_login)
                if not author_login:
                    author_login = m_unknown_username
                one_result["author"] = author_login
                if author_email:
                    one_result["author_email"] = author_email
                if author_name:
                    one_result["author_name"] = author_name
                if commit_sha:
                    #print ("SHA: %s" % commit_sha)
                    one_result["sha"] = commit_sha
                    commit_details = get_commit_details(scheme, host, base_path, owner, repo, commit_sha, git_token)
                    if commit_details:
                        # Handle case where commit must be ignored.
                        if len(commit_details.keys()) > 0:

                            #print ("    Date: %s" % commit_details["date"])
                            #print ("    Additions: %s" % commit_details["stats"]["additions"])
                            #print ("    Deletions: %s" % commit_details["stats"]["deletions"])
                            #print ("    Difference: %s" % commit_details["stats"]["difference"])
                            #print ("    Total: %s" % commit_details["stats"]["total"])

                            one_result["date"] = commit_details["date"]

                            one_result["stats"] = commit_details["stats"]
                            d = datetime.datetime.strptime(commit_details["date"], "%Y-%m-%dT%H:%M:%SZ")

                            # It seems that even if the 'since' is properly set when using the API, sometimes
                            # commits before that date are retrieved. That might be due to what is discussed
                            # here: https://stackoverflow.com/questions/27036387/git-log-not-chronologically-ordered
                            # In any case, that can be problematic when recovering from the cache as one might retrieve
                            # a commit that was already in the cache, hence ending up duplicating it.
                            # In order to avoid that, one must check if that commit is already there when using the cache.
                            if original_since_date and d < original_since_date:
                                print("    Commit is before 'since' date, so ignoring: %s" % commit_sha)
                                continue
                            elif since_date and d < since_date and from_cache:
                                print("    Commit is before highest date from cache, need to check if it is a duplicate: %s" % commit_sha)
                                duplicate_found = False
                                for author_cache in from_cache[0].keys():
                                    for author_entries in from_cache[0][author_cache]:
                                        if "sha" in author_entries and author_entries["sha"] == commit_sha:
                                            duplicate_found = True
                                            break
                                    if duplicate_found:
                                        break
                                if duplicate_found:
                                    print("        Is a duplicate, ignoring it")
                                    continue
                                else:
                                    print("        Not a duplicate, keeping it")
                                # This can be a bit time consuming unfortunately.

                            one_result['date_unix'] = unix_time_millis(d)
                            one_result['owner'] = owner
                            one_result['repo'] = repo
                            one_result['branch'] = branch
                            if author_login in result:
                                result[author_login].append(one_result)
                            else:
                                a = []
                                a.append(one_result)
                                result[author_login] = a

                else:
                    print ("    Commit SHA could not be found in: \n\n%s" % json.dumps(one_js, indent=4, sort_keys=True))

                counter = counter + 1
                if (counter % 20 == 0):

                    print ("    Nb commits processed so far: %d (latest date: %s)" % (counter, datetime.datetime.strptime(one_result["date"], "%Y-%m-%dT%H:%M:%SZ").strftime(m_csv_date_format)))

        else:
            print ("    Erreur retrieving commits (status code: %d) at %s" % (status_code, next_url))
            return None

    # Only update cache if needed.
    if (counter != nb_cache):
        cache(cache_url, result)
    print ("    Done processing commits (total nb commits processed: %d)" % counter)
    return result

def sort_results(r):
    """Sorts a list containg commit information by date, thanks to the 'date_unix' field.

    Example list with one item below. The result will have items sorted by 'date_unix' ascending.

    [
        {
            "sha": "6b9b8c59703560f197c71adfe0ac9770cfeffb33",
            "date": "2011-04-14T16:00:49Z",
            "date_unix": "1302796849000.0",
            "author": "jdoe",
            "author_name": "John Doe",
            "author_email": "jdoe@testmail.com",
            "owner": "MyOrg",
            "repo": "MyRepo",
            "branch": "master",
            "stats" : {
                "additions" : 23,
                "deletions" : 12,
                "total"     : 35,
                "difference": 11
            }
        }
    ]
    """
    return sorted(r, key=lambda k: k['date_unix'], reverse=False)

def merge_sort_results(dict):
    """Merges all values of a dict (which are lists) into one single list, then sorts it and returns it.

    See sort_results(r) for details about sorting.
    """
    result = []
    for x in dict.keys():
        #print ("X: %s" % x)
        #print (json.dumps(r[x], indent=4, sort_keys=True))
        result.extend(dict[x])
    return sort_results(result)

# appends r2 values to r1 values.
def combine_results(dict1, dict2):
    """Adds dict2 values into dict1 and returns dict1.

    Both dictionaries have String as keys and List as values.
    For all key/value in dict2:
        - if the same key exists in dict1 then extend its value with the value in dict2.
        - if dict1 does not contain that key, then add it with the value of the key in dict2.
    Returns dict1 if dict2 is None.
    """
    if not dict1:
        return dict2
    else:
        for x in dict2.keys():
            if x in dict1:
                dict1[x].extend(dict2[x])
            else:
                dict1[x] = dict2[x]
        return dict1

def process_unknown(r):
    """Identifies and processes commits with author '<unknown>' and processes them
    according to the relevant parameters.

    For every entry whose author is currently '<unknown>':
    - If email to author or name to author files have been specified, then we try to
      set the author to the mapping specified in that file (email takes precendence).
    - If no mapping could be found and name is available, then use name.
    - If no mapping could be found and name is not available, then use email.
    - If no mapping could be found and name is not available and email is not
      available, then keep it as '<unknown>'.
    """
    # Tries to find the actual user thanks to email/name mapping files.
    # Also reports an issue if unknown is not allowed and no mapping is found.
    if m_unknown_username in r and r[m_unknown_username]:
        print ("Processing '%s' user data" % m_unknown_username)
        unknown_data = r[m_unknown_username]
        new_unknown_data = []
        for x in unknown_data:
            author = None
            author_email = None
            author_name = None
            if "author_email" in x and x["author_email"]:
                author_email = x["author_email"]
            if "author_name" in x and x["author_name"]:
                author_name = x["author_name"]
            if author_email and author_email.lower() in m_email_to_author and m_email_to_author[author_email.lower()]:
                author = m_email_to_author[author_email.lower()]
                #print("    Found author thanks to email to author file: %s --> %s (%s/%s: %s)" % (author_email, author, x["owner"], x["repo"], x["sha"]))
            elif not author and author_name and author_name.lower() in m_name_to_author and m_name_to_author[author_name.lower()]:
                author = m_name_to_author[author_name.lower()]
                #print("    Found author thanks to name to author file: %s --> %s (%s/%s: %s)" % (author_name, author, x["owner"], x["repo"], x["sha"]))
            elif not author and author_name:
                author = author_name
                #print("    No mapping found, using name: %s (%s/%s: %s)" % (author_name, x["owner"], x["repo"], x["sha"]))
            elif not author and author_email:
                author = author_email
                #print("    No mapping found, using email: %s (%s/%s: %s)" % (author_email, x["owner"], x["repo"], x["sha"]))
            else:
                new_unknown_data.append(x)
                print("    Author could not be found and no name or email available, keeping it as '%s' (%s/%s: %s)" % (m_unknown_username, x["owner"], x["repo"], x["sha"]))
            if author:
                x["author"] = author
                if not author in r:
                    r[author] = []
                r[author].append(x)

        if len(new_unknown_data) > 0:
            r[m_unknown_username] = new_unknown_data
        else:
            r.pop(m_unknown_username)

    return r

def get_top_contributors(dict, nb):
    """Returns a list containing the names of the nb top contibutors.

    A contributor is evaulated by the total difference at its latest commit.
    """
    if not dict or not len(dict.keys()) or not nb:
        return None
    else:
        print("Calculating top contributors")
        max_contribs = []
        for k in dict.keys():
            author_data = sort_results(dict[k])
            author_contrib = {}
            author_contrib["author"] = k
            if len(author_data) > 0 and "total_stats_author" in author_data[len(author_data) - 1] and "difference" in author_data[len(author_data) - 1]["total_stats_author"]:
                print("    Author % s contrib: %d" % (k, author_data[len(author_data) - 1]["total_stats_author"]["difference"]))
                author_contrib["difference"] = author_data[len(author_data) - 1]["total_stats_author"]["difference"]
            else:
                #author_contrib["difference"] = 0
                raise ValueError('Total statistics not found for author %s' % k)
            max_contribs.append(author_contrib)
        max_contribs = sorted(max_contribs, key=lambda k: k['difference'], reverse=True)
        to_keep = max_contribs[:nb]
        no_keep = max_contribs[nb:]
        if to_keep:
            print("    Top contributors (in alphabetical order):\n        %s" % "\n        ".join(sorted([i["author"] for i in to_keep], key=str.lower)))
        #if no_keep:
        #    print("    Not Keeping:\n        %s" % "\n        ".join(sorted([i["author"] for i in no_keep], key=str.lower)))

        return [i["author"] for i in to_keep]

def replace_hidden_with_others(dict, top_contributors, authors_to_show):
    """Returns a tuple with the updated dict and the list of removed contributors.

    The first item is the dict udpated where all authors not in
    top_contributors have been removed and replaced with one single OTHERS authors which
    contains all their commits.

    The second item is the list of authors who have been removed.
    """
    if not dict or not len(dict.keys()):
        return (dict, [])
    else:
        print("Replacing authors to hide with %s" % m_others_username)
        others_data = []
        to_remove_authors = []
        for k in dict.keys():
            if (top_contributors != None and k not in top_contributors) or (authors_to_show != None and k not in authors_to_show):
                others_data.extend(dict[k])
                to_remove_authors.append(k)
        if len(to_remove_authors) > 0:
            print("    Replaced %d author(s)" % len(to_remove_authors))
            for to_remove in to_remove_authors:
                if to_remove in dict:
                    dict.pop(to_remove)
            if len(others_data) > 0:
                # Do not forget to sort and recalculate totals that have changed obviously.
                dict[m_others_username] = populate_totals(sort_results(others_data))
        else:
            print("    Nothing to do")

        return (dict, to_remove_authors)

def init_html_data(html_data, chart_type, title, author):
    """Init the html_data object used for generting the HTML output for a
    given chart_type and author. Returns the udpated html_data object.
    """
    if not chart_type in html_data:
        html_data[chart_type] = {}
        html_data[chart_type]["authors"] = {}
        html_data[chart_type]["title"] = title
    html_data[chart_type]["authors"][author] = {}
    html_data[chart_type]["authors"][author]["data"] = []
    html_data[chart_type]["authors"][author]["label"] = author

    return html_data

def populate_html_data(html_data, html_object, chart_type, author, y, plus_minus):
    """Adds an entry (i.e. data point) to the html_data object used for generting
    the HTML output for a given chart_type and author. Returns the udpated html_data object.

    Note that a deep copy of the given html_object is created and used instead of
    using it directly.
    TODO: this means that the current data structure contains a lot of duplicate
    information and should be optimized/reworked.
    """
    h = copy.deepcopy(html_object)
    h["y"] = y
    # The 'plus_minus' values allow to display the impact of a single
    # commit in the tooltip (the 'y' value is the sum over time, which
    # is what the graph shows).
    h["plus_minus"] = plus_minus
    html_data[chart_type]["authors"][author]["data"].append(h)
    return html_data

#######################################################################
print("GREVOS")
print("------\n")

#######################################################################
# argparse stuff to parse input parameters.

parser = argparse.ArgumentParser(description='Generate combined activity graphs for any number of repositories.')
parser.add_argument('-f', '--file', type=str, nargs=1, help='File containing the repos to process. Format: <scheme>,<host>,<base_path>,<org>,<repo>,<branch>,<commit_url_pattern>,<since>,<api_token>[,<commits_to_ignore>]. <commits_to_ignore> is a %s separated list of SHA commits.' % m_commits_to_ignore_separator)
parser.add_argument('-i', '--ignore_files', type=str, nargs='*', help=argparse.SUPPRESS)
parser.add_argument('-a', '--authors', type=str, nargs='*', help='Only outputs statistics for the specified authors (all authors by default).')
parser.add_argument('-o', '--output_folder', type=str, nargs='?', help='Folder where the generated CSV files are stored, default: \'%s\'.' % m_output_folder)
parser.add_argument('-c', '--cache_folder', type=str, nargs='?', help='Folder where cache files are stored, default: \'%s\'.' % m_cache_folder)
parser.add_argument('-oc', '--output_commits', type=str2bool, nargs='?', default=True, help='Outputs nb commits in genereted files, default: yes.')
parser.add_argument('-oa', '--output_additions', type=str2bool, nargs='?', default=True, help='Outputs additions in genereted files, default: yes.')
parser.add_argument('-od', '--output_deletions', type=str2bool, nargs='?', default=True, help='Outputs deletions in genereted files, default: yes.')
parser.add_argument('-odi', '--output_differences', type=str2bool, nargs='?', default=True, help='Outputs differences (i.e. additions - deletions) in genereted files, default: yes.')
parser.add_argument('-ot', '--output_totals', type=str2bool, nargs='?', default=True, help='Outputs totals (i.e. additions + deletions) in genereted files, default: yes.')
parser.add_argument('-d', '--csv_date_format', type=str, nargs='?', help='Date format in the generated CSV, default: \'%s\'.' % m_csv_date_format.replace('%', '%%'))
parser.add_argument('-eaf', '--email_to_author_file', type=str, nargs='?', help='File providing the mapping between email and username, useful when the username is not available in the Git commit but the email is. File format: one entry per line, first item is the email, second item is the username, separated by a comma.')
parser.add_argument('-naf', '--name_to_author_file', type=str, nargs='?', help='File providing the mapping between name and username, useful when the username is not available in the Git commit but the name is. File format: one entry per line, first item is the name, second item is the username, separated by a comma.')
parser.add_argument('-macd', '--max_commit_difference', type=int, nargs='?', help='Max difference of a commit (i.e. additions - deletions) for it to be considered, default: no limit. This is useful to exclude commits that do not make sense to take into account because many files were copied into the repository (e.g. JavaScript files in node.js projects).')
parser.add_argument('-micd', '--min_commit_difference', type=int, nargs='?', help='Min difference of a commit (i.e. additions - deletions) for it to be considered, default: no limit. This is useful to exclude commits that do not make sense to take into account because many files were removed from the repository (e.g. JavaScript files in node.js projects).')
parser.add_argument('-tc', '--top_contributors', type=int, nargs='?', help='Only keep the n top contributors based on the number of (additions - deletions), default: keep all.')
parser.add_argument('-mph', '--max_points_html', type=int, nargs='?', help='Maximum number of points in the HTML output. A graph with too many points will not offer a good user experience.')


args = parser.parse_args()

# Check/validate parameters.
if not args.file:
    print ('file not specified (use -h for details)')
    exit(1)
elif len(args.file) != 1:
    print ('one single source file allowed (use -h for details)')
    exit(1)
elif not os.path.exists(args.file[0]):
    print ('file does not exist: %s' % args.file[0])
    exit(1)
if args.output_folder:
    m_output_folder = args.output_folder
if args.cache_folder:
    m_cache_folder = args.cache_folder
if args.csv_date_format:
    m_csv_date_format = args.csv_date_format
if args.email_to_author_file:
    if not os.path.exists(args.email_to_author_file):
        print ('file does not exist: %s' % args.email_to_author_file)
        exit(1)
    m_email_to_author_file = args.email_to_author_file
if args.name_to_author_file:
    if not os.path.exists(args.name_to_author_file):
        print ('file does not exist: %s' % args.name_to_author_file)
        exit(1)
    m_name_to_author_file = args.name_to_author_file
if args.top_contributors != None:
    if args.top_contributors < 1:
        print ('number of top contributors must be a positive integer')
        exit(1)
if args.max_points_html != None:
    if args.max_points_html < 1:
        print ('max number of points in HTML must be a positive integer')
        exit(1)

print ("Source file: %s" % args.file[0])
print ("Output folder: %s" % m_output_folder)
print ("Cache folder: %s" % m_cache_folder)

if m_email_to_author_file:
    print ("Email to author file: %s" % m_email_to_author_file)
    eof_reader = csv.reader(open(m_email_to_author_file, newline=''), delimiter=',', quotechar='|')
    for row in eof_reader:
        if (len(row) != 2):
            print ('wrong file format: %s (line: %s)' % (m_email_to_author_file, ",".join(row)))
            exit(1)
        m_email_to_author[row[0].lower()] = row[1]
if m_name_to_author_file:
    print ("Name to author file: %s" % m_name_to_author_file)
    eof_reader = csv.reader(open(m_name_to_author_file, newline=''), delimiter=',', quotechar='|')
    for row in eof_reader:
        if (len(row) != 2):
            print ('wrong file format: %s (line: %s)' % (m_name_to_author_file, ",".join(row)))
            exit(1)
        m_name_to_author[row[0].lower()] = row[1]

#######################################################################
# Start of actual processing.
result = None
to_process = []
repos_html = []

# Read source files and do some validation.
csv_reader = csv.reader(open(args.file[0], newline=''), delimiter=',', quotechar='|')
for row in csv_reader:
    if len(row) < 9 or len(row) > 10:
        print ('wrong file format: %s (line: %s)' % (args.file[0], ",".join(row)))
        exit(1)
    repos_html.append("%s/%s (%s)" % (row[3], row[4], row[5]))
    to_process.append(row)

if len(to_process) == 0:
    print("No repository to process")
    exit(1)

print("Nb repos to process: %d\n" % len(to_process))

# Processes all entries in the source file.
commits_to_ignore = []
commits_url_patterns = {}
for idx, row in enumerate(to_process, 1):
    # Commits to ignore are optional.
    if len(row) == 10:
         commits_to_ignore.extend(row[9].split(m_commits_to_ignore_separator))
    owner = row[3]
    repo = row[4]
    commit_url_pattern = row[6]
    a = get_rep_stats(row[0], row[1], row[2], owner, repo, row[5], row[7], row[8], idx, len(to_process))
    if commit_url_pattern:
        commits_url_patterns["%s/%s" % (owner, repo)] = commit_url_pattern
    # If None is returned, something went wrong.
    if a == None:
        exit(1)
    result = combine_results(result, a)

# Do the necessary post-processing.
# Note that this is done *after* date from local cache is leveraged, i.e. we can
# quickly generate graphs with different parameters while reusing the data in teh cache.
result = process_unknown(result)
result = remove_commits_to_ignore(result, args.min_commit_difference, args.max_commit_difference, commits_to_ignore)

# Sort and populate totals once all repos have been processed.
for x in result:
    a = result[x]
    #print (json.dumps(a, indent=4, sort_keys=True))
    a = sort_results(a)
    a = populate_totals(a)
    result[x] = a


# Start generating the output files.
if result and len(result) > 0:

    csv_output_filename = get_csv_output_filename_with_path(args.file[0])
    with open(csv_output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        row = []
        row.append("Date")

        authors_pos = {}
        authors_hidden = []



        # This object will be used to generate the HTML output, which is generated
        # with a jinja2 template.
        # Example of what this object looks like is available in docs/html_data_example.json.
        # TODO: the current data structure contains a lot of duplicate information and should
        # be optimized/reworked.
        html_data = {}

        top_contributors = get_top_contributors(result, args.top_contributors)
        (result, authors_hidden) = replace_hidden_with_others(result, top_contributors, args.authors)

        # Note that we add fictive 'TOTAL' user to see general trend.
        # This includes all commits, even those from the authors that are not displayed.
        # It does not include hidden commits though (e.g. commits removed because too big
        # or explicitely excluded).
        authors = sorted(result.keys(), key=str.lower)

        authors.append(m_total_username)
        for author in authors:
            authors_pos[author] = len(authors_pos.keys()) + 1
            # Headers depends on the author to include and on the
            # on the data to be included (additions, deletions,...).
            if args.output_commits:
                row.append("%s (commits)" % author)
                html_data = init_html_data(html_data, "nb_commits", "Number of commits", author)
            if args.output_additions:
                row.append("%s (additions)" % author)
                html_data = init_html_data(html_data, "additions", "Additions", author)
            if args.output_deletions:
                row.append("%s (deletions)" % author)
                html_data = init_html_data(html_data, "deletions", "Deletions", author)
            if args.output_differences:
                row.append("%s (difference)" % author)
                html_data = init_html_data(html_data, "difference", "Difference", author)
            if args.output_totals:
                row.append("%s (total)" % author)
                html_data = init_html_data(html_data, "total", "Total", author)

        nb_fields_per_author = sum([args.output_commits, args.output_additions, args.output_deletions, args.output_differences, args.output_totals])

        #print("Nb fields per author: %d" % nb_fields_per_author)

        row.append("Repository")
        row.append("Commit SHA")
        row.append("Commit URL")

        writer.writerow(row)

        # Totals for user TOTAL are calculated as we generate the CSV file.
        total_nb_commits = 0
        total_additions = 0
        total_deletions = 0
        total_difference = 0
        total_total = 0

        # Loop through all commits, ordered by date.
        for one_result in merge_sort_results(result):
            the_author = one_result["author"]
            is_others = the_author in authors_hidden

            if is_others:
                the_author = m_others_username


            row = []
            the_date = datetime.datetime.strptime(one_result["date"], "%Y-%m-%dT%H:%M:%SZ")
            row.append(the_date.strftime(m_csv_date_format))

            # This object will be deep copied for each line to generate in the graph
            # for this author (e.g. the additions line if additions must be rendered, the
            # deletions line if deletions must be rendered,...).
            # Each deep copy has its own 'y' value obviously.
            html_object = {}
            html_object["year"] = the_date.year
            # -1 because months are 0-indexed in JavaScript.
            html_object["month"] = the_date.month - 1
            html_object["day"] = the_date.day
            html_object["hours"] = the_date.hour
            html_object["minutes"] = the_date.minute
            html_object["seconds"] = the_date.second

            html_object["owner"] = one_result["owner"]
            html_object["repo"] = one_result["repo"]
            html_object["branch"] = one_result["branch"]
            html_object["sha"] = one_result["sha"]
            # We only 'author' to OTHERS and TOTAL It would be redundent to show it for
            # every user at it is already displayed in the tooltip.
            if is_others:
                html_object["author"] = one_result["author"]

            owner_repo = "%s/%s" % (one_result["owner"], one_result["repo"])
            commit_url = None
            if owner_repo in commits_url_patterns:
                commit_url = commits_url_patterns[owner_repo].replace("{{owner}}", one_result["owner"]).replace("{{repository}}", one_result["repo"]).replace("{{commit_sha}}", one_result["sha"])
                # This allows to have a HREF link pointing to the actual GitHub commit page when clicking
                # on the data point in the generated graph.
                html_object["commit_url"] = commit_url
            # Show branch in output.
            owner_repo = "%s (%s)" % (owner_repo, one_result["branch"])


            # Add empty cells to add in the right column.
            for x in range(0, authors_pos[the_author] - 1):
                for y in range(0, nb_fields_per_author):
                    row.append("")

            if args.output_commits:
                row.append(one_result["total_stats_author"]["nb_commits"])
                html_data = populate_html_data(html_data, html_object, "nb_commits", the_author, one_result["total_stats_author"]["nb_commits"], 1)
            if args.output_additions:
                row.append(one_result["total_stats_author"]["additions"])
                html_data = populate_html_data(html_data, html_object, "additions", the_author, one_result["total_stats_author"]["additions"], one_result["stats"]["additions"])
            if args.output_deletions:
                row.append(one_result["total_stats_author"]["deletions"])
                html_data = populate_html_data(html_data, html_object, "deletions", the_author, one_result["total_stats_author"]["deletions"], one_result["stats"]["deletions"])
            if args.output_differences:
                row.append(one_result["total_stats_author"]["difference"])
                html_data = populate_html_data(html_data, html_object, "difference", the_author, one_result["total_stats_author"]["difference"], one_result["stats"]["difference"])
            if args.output_totals:
                row.append(one_result["total_stats_author"]["total"])
                html_data = populate_html_data(html_data, html_object, "total", the_author, one_result["total_stats_author"]["total"], one_result["stats"]["total"])

            # len() -1 because oF TOTAL user that we must not take into account.
            for x in range(authors_pos[the_author], len(authors_pos)-1):
                for y in range(0, nb_fields_per_author):
                    row.append("")

            # Add fictive 'TOTAL' user to see general trend.
            total_nb_commits = total_nb_commits + 1
            total_additions = total_additions + one_result["stats"]["additions"]
            total_deletions = total_deletions + one_result["stats"]["deletions"]
            total_difference = total_difference + one_result["stats"]["difference"]
            total_total = total_total + one_result["stats"]["total"]

            # This will only add the 'author' to TOTAL since we create deep
            # copies of html_object. It would be redundent to show it for
            # every user at it is already displayed in the tooltip.
            html_object["author"] = the_author;

            if args.output_commits:
                row.append(total_nb_commits)
                html_data = populate_html_data(html_data, html_object, "nb_commits", m_total_username, total_nb_commits, 1)
            if args.output_additions:
                row.append(total_additions)
                html_data = populate_html_data(html_data, html_object, "additions", m_total_username, total_additions, one_result["stats"]["additions"])
            if args.output_deletions:
                row.append(total_deletions)
                html_data = populate_html_data(html_data, html_object, "deletions", m_total_username, total_deletions, one_result["stats"]["deletions"])
            if args.output_differences:
                row.append(total_difference)
                html_data = populate_html_data(html_data, html_object, "difference", m_total_username, total_difference, one_result["stats"]["difference"])
            if args.output_totals:
                row.append(total_total)
                html_data = populate_html_data(html_data, html_object, "total", m_total_username, total_total, one_result["stats"]["total"])

            # Show the repo this commit is comming from.
            row.append(owner_repo)
            row.append("%s" % one_result["sha"])
            if commit_url:
                row.append("%s" % commit_url)
                html_object["commit_url"] = commit_url
            else:
                row.append("")

            writer.writerow(row)

        print("Output file generated: %s" % csv_output_filename)

        # Create the jinja2 environment.
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('chart.html')
        html_data_values = {}
        for chart_type in html_data.keys():
            html_data_values
            list(html_data.values())

        # This max_points_divide_factor allows to get close to the max number
        # of points requested by the user, but we might have more or less, which
        # is not big deal.
        # Also, the technic we use to limit the number of points in the graph is to
        # simply render one out of max_points_divide_factor, which is basic and might
        # not properly show peaks and valleys. But that should be fine in most cases.
        max_points_divide_factor = 1
        if args.max_points_html and html_data.keys():
            total_nb_points = 0
            temp_list = list(html_data.values())[0]["authors"]
            for hdv in temp_list.values():
                if "data" in hdv:
                    total_nb_points = total_nb_points + len(hdv["data"])
            if total_nb_points > args.max_points_html:
                max_points_divide_factor = int(total_nb_points / args.max_points_html)

        #print (json.dumps(html_data, indent=4, sort_keys=True))

        output_from_parsed_template = template.render(labels_and_data=html_data,
                                                      generation_date=m_now.strftime(m_csv_date_format),
                                                      repositories=sorted(repos_html, key=str.lower),
                                                      authors_hidden=sorted(authors_hidden, key=str.lower),
                                                      max_points_divide_factor=max_points_divide_factor,
                                                      title=get_html_title(args.file[0]))

        # to save the results
        html_output_filename = get_html_output_filename_with_path(args.file[0])
        with open(html_output_filename, "w") as fh:
            fh.write(output_from_parsed_template)

        print("Output file generated: %s" % html_output_filename)

        print("    Total nb authors: %d" % (len(authors_hidden) + len(authors_pos.keys())))
        if len(authors_hidden) > 0:
            print("    OTHERS include the following authors:\n        %s" % "\n        ".join(sorted(authors_hidden, key=str.lower)))

print ('\nDone.')
# Everything went fine.
exit(0)
