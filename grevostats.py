'''
Usage:
Just run with the necessary arguments (-h for details).
'''
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


print("GREVOS")
print("------\n")

# Need to be manually updated. Should allow to prevent using old JSON cache
# when the schema has been modified with a new version.
schema_version = 2
cache_folder = 'cache'
output_folder = 'output'
output_additions = True
output_deletions = True
output_differences = True
output_totals = True
output_commits = True
csv_date_format = "%m/%d/%Y %H:%M:%S"
email_to_author_file = None
email_to_author = {}
name_to_author_file = None
name_to_author = {}
unknown_username = "<unknown>"
commits_to_ignore_separator = "-"
now = datetime.datetime.now()

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

parser = argparse.ArgumentParser(description='Generate combined activity graphs for any number of repositories.')
parser.add_argument('-f', '--file', type=str, nargs=1, help='File containing the repos to process. Format: <scheme>,<host>,<base_path>,<org>,<repo>,<branch>,<commit_url_pattern>,<since>,<api_token>[,<commits_to_ignore>]. <commits_to_ignore> is a %s separated list of SHA commits.' % commits_to_ignore_separator)
parser.add_argument('-i', '--ignore_files', type=str, nargs='*', help=argparse.SUPPRESS)
parser.add_argument('-a', '--authors', type=str, nargs='*', help='Only outputs statistics for the specified authors (all authors by default).')
parser.add_argument('-o', '--output_folder', type=str, nargs='?', help='Folder where the generated CSV files are stored, default: \'%s\'.' % output_folder)
parser.add_argument('-c', '--cache_folder', type=str, nargs='?', help='Folder where cache files are stored, default: \'%s\'.' % cache_folder)
parser.add_argument('-oc', '--output_commits', type=str2bool, nargs='?', default=True, help='Outputs nb commits in genereted files, default: yes.')
parser.add_argument('-oa', '--output_additions', type=str2bool, nargs='?', default=True, help='Outputs additions in genereted files, default: yes.')
parser.add_argument('-od', '--output_deletions', type=str2bool, nargs='?', default=True, help='Outputs deletions in genereted files, default: yes.')
parser.add_argument('-odi', '--output_differences', type=str2bool, nargs='?', default=True, help='Outputs differences (i.e. additions - deletions) in genereted files, default: yes.')
parser.add_argument('-ot', '--output_totals', type=str2bool, nargs='?', default=True, help='Outputs totals (i.e. additions + deletions) in genereted files, default: yes.')
parser.add_argument('-d', '--csv_date_format', type=str, nargs='?', help='Date format in the generated CSV, default: \'%s\'.' % csv_date_format.replace('%', '%%'))
parser.add_argument('-eaf', '--email_to_author_file', type=str, nargs='?', help='File providing the mapping between email and username, useful when the username is not available in the Git commit but the email is. File format: one entry per line, first item is the email, second item is the username, separated by a comma.')
parser.add_argument('-naf', '--name_to_author_file', type=str, nargs='?', help='File providing the mapping between name and username, useful when the username is not available in the Git commit but the name is. File format: one entry per line, first item is the name, second item is the username, separated by a comma.')
parser.add_argument('-au', '--allow_unkwnown_author', type=str2bool, nargs='?', default=True, help='Assigns commits whose author login cannot be retrieved to user \'%s\' if enabled, makes an error and stops processing otherwise, default: yes.' % unknown_username)
parser.add_argument('-macd', '--max_commit_difference', type=int, nargs='?', help='Max difference of a commit (i.e. additions - deletions) for it to be considered, default: no limit. This is useful to exclude commits that do not make sense to take into account because many files were copied into the repository (e.g. JavaScript files in node.js projects).')
parser.add_argument('-micd', '--min_commit_difference', type=int, nargs='?', help='Min difference of a commit (i.e. additions - deletions) for it to be considered, default: no limit. This is useful to exclude commits that do not make sense to take into account because many files were removed from the repository (e.g. JavaScript files in node.js projects).')
parser.add_argument('-tc', '--top_contributors', type=int, nargs='?', help='Only keep the n top contributors based on the number of (additions - deletions), default: keep all.')
parser.add_argument('-mph', '--max_points_html', type=int, nargs='?', help='Maximum number of points in the HTML output. A graph with too many points will not offer a good user experience.')


args = parser.parse_args()

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
    output_folder = args.output_folder
if args.cache_folder:
    cache_folder = args.cache_folder
if args.csv_date_format:
    csv_date_format = args.csv_date_format
if args.email_to_author_file:
    if not os.path.exists(args.email_to_author_file):
        print ('file does not exist: %s' % args.email_to_author_file)
        exit(1)
    email_to_author_file = args.email_to_author_file
if args.name_to_author_file:
    if not os.path.exists(args.name_to_author_file):
        print ('file does not exist: %s' % args.name_to_author_file)
        exit(1)
    name_to_author_file = args.name_to_author_file
if args.top_contributors != None:
    if args.top_contributors < 1:
        print ('number of top contributors must be a positive integer')
        exit(1)
if args.max_points_html != None:
    if args.max_points_html < 1:
        print ('max number of points in HTML must be a positive integer')
        exit(1)

print ("Source file: %s" % args.file[0])
print ("Output folder: %s" % output_folder)
print ("Cache folder: %s" % cache_folder)
#print ("CSV date format: %s" % csv_date_format)
if email_to_author_file:
    print ("Email to author file: %s" % email_to_author_file)
    eof_reader = csv.reader(open(email_to_author_file, newline=''), delimiter=',', quotechar='|')
    for row in eof_reader:
        if (len(row) != 2):
            print ('wrong file format: %s (line: %s)' % (args.email_to_author_file, ",".join(row)))
            exit(1)
        email_to_author[row[0].lower()] = row[1]
if name_to_author_file:
    print ("Name to author file: %s" % name_to_author_file)
    eof_reader = csv.reader(open(name_to_author_file, newline=''), delimiter=',', quotechar='|')
    for row in eof_reader:
        if (len(row) != 2):
            print ('wrong file format: %s (line: %s)' % (args.name_to_author_file, ",".join(row)))
            exit(1)
        name_to_author[row[0].lower()] = row[1]

direct_dependencies_cache = {}
recursive_dependencies_cache = {}


epoch = datetime.datetime.utcfromtimestamp(0)

def unix_time_millis(dt):
    return (dt - epoch).total_seconds() * 1000

def get_commit_details(scheme, host, base_path, owner, repo, commit_sha, git_token):
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

def remove_commits_to_ignore(r, commits_to_ignore):
    if r and len(r.keys()) and commits_to_ignore and len(commits_to_ignore) > 0:
        print("Removing commits to ignore")
        for k in r.keys():
            author_data = r[k]
            to_remove_indexes = []
            for idx, x  in enumerate(author_data):
                if "stats" in x and "difference" in x["stats"] and args.max_commit_difference != None and x["stats"]["difference"] > args.max_commit_difference:
                    print("    Removing commit because it is above the max difference limit in %s/%s: %s (%d)" % (x["owner"], x["repo"], x["sha"], x["stats"]["difference"]))
                    to_remove_indexes.append(idx)
                elif "stats" in x and "difference" in x["stats"] and args.min_commit_difference != None and x["stats"]["difference"] < args.min_commit_difference :
                    print("    Removing commit because it is below the min difference limit in %s/%s: %s (%d)" % (x["owner"], x["repo"], x["sha"], x["stats"]["difference"]))
                    to_remove_indexes.append(idx)
                elif "sha" in x and x["sha"] in commits_to_ignore:
                    print("    Removing commit to ignore in %s/%s: %s" % (x["owner"], x["repo"], x["sha"]))
                    to_remove_indexes.append(idx)
            for idx in reversed(to_remove_indexes):
                del author_data[idx]
    return r

def populate_totals(the_array):
    if the_array:
        previous = None
        for one_item in the_array:
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
        return the_array
    else:
        return the_array

def get_csv_output_filename():
    return get_output_filename("csv")

def get_html_output_filename():
    return get_output_filename("html")

def get_output_filename(extension):
    base_name = os.path.basename(args.file[0])
    if base_name.find('.') > 0:
        base_name = base_name[:base_name.find('.')]
    return '%s_%s.%s' % (base_name, now.strftime("%Y%m%d%H%M%S"), extension)

def get_html_title():
    base_name = os.path.basename(args.file[0])
    if base_name.find('.') > 0:
        base_name = base_name[:base_name.find('.')]
    return base_name.replace('_', ' ').replace('-', ' ').upper()

def get_csv_output_filename_with_path():
    return get_filename_with_path(get_csv_output_filename(), output_folder)

def get_html_output_filename_with_path():
    return get_filename_with_path(get_html_output_filename(), output_folder)

def get_filename_with_path(filename, folder):
    return "%s%s%s" % (folder, "" if folder.endswith("/") else "/", filename)

def get_cache_filename(url):
    # Important to take args.ignore_files into account as the result depends on this parameter.
    cache_filename = hashlib.sha1(("%s%s%d" % (url, ",".join(args.ignore_files) if args.ignore_files else "", schema_version)).encode('utf-8')).hexdigest()
    #print("Cache filename: %s" % cache_filename)
    return cache_filename

def get_cache_filename_with_path(url):
    return get_filename_with_path(get_cache_filename(url), cache_folder)

# Creates/overwrites the file with the given json.
def cache(url, the_json):
    #print ("    Caching: %s" % url)
    with open(get_cache_filename_with_path(url), 'w') as outfile:
        json.dump(the_json, outfile)

# Returns a tuple (JSON, highest_date, sha, nb_commits), where highest_date is the date of the
# most recent commit in the JSON and sha the SHA for that most recent commit.
# Returns None if no cache file exists.
def load_cache(url):
    cache_file = get_cache_filename_with_path(url)
    if not os.path.exists(cache_file):
        print("    No cache (file does not exist: %s)" % cache_file)
        return None
    else:
        print("    Cache found (file: %s)" % cache_file)
        try:
            with open(cache_file) as json_data:
                d = json.load(json_data)
                merged_results = merge_results(d)
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




def get_rep_stats(scheme, host, base_path, owner, repo, branch, commit_url_pattern, since, git_token, index_repo, total_nb_repos):
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
    result = {}

    from_cache = load_cache(cache_url)
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
                    author_login = unknown_username
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

                    print ("    Nb commits processed so far: %d (latest date: %s)" % (counter, datetime.datetime.strptime(one_result["date"], "%Y-%m-%dT%H:%M:%SZ").strftime(csv_date_format)))

        else:
            print ("    Erreur retrieving commits (status code: %d) at %s" % (status_code, next_url))
            return None

    print ("    Done processing commits (total nb commits processed: %d)" % counter)
    cache(cache_url, result)
    return result

def sort_results(r):
    return sorted(r, key=lambda k: k['date_unix'], reverse=False)

def merge_results(r):
    result = []
    for x in r.keys():
        #print ("X: %s" % x)
        #print (json.dumps(r[x], indent=4, sort_keys=True))
        result.extend(r[x])
    return sort_results(result)

# appends r2 values to r1 values.
def combine_results(r1, r2):
    if not r1:
        return r2
    else:
        for x in r2.keys():
            if x in r1:
                r1[x].extend(r2[x])
            else:
                r1[x] = r2[x]
        return r1

# Tries to find the actual user thanks to email/name mapping files.
# Also reports an issue if unknown is not allowed and no mapping is found.
def process_unknown(r):
    if unknown_username in r and r[unknown_username]:
        print ("Processing '%s' user data" % unknown_username)
        unknown_data = r[unknown_username]
        new_unknown_data = []
        for x in unknown_data:
            author_login = None
            author_email = None
            author_name = None
            if "author_email" in x and x["author_email"]:
                author_email = x["author_email"]
            if "author_name" in x and x["author_name"]:
                author_name = x["author_name"]
            if author_email and author_email.lower() in email_to_author and email_to_author[author_email.lower()]:
                author_login = email_to_author[author_email.lower()]
                print("    Found author thanks to email to author file: %s --> %s" % (author_email, author_login))
            elif not author_login and author_name.lower() in name_to_author and name_to_author[author_name.lower()]:
                author_login = name_to_author[author_name.lower()]
                print("    Found author thanks to name to author file: %s --> %s" % (author_name, author_login))
            else:
                print("    Author could not be found (email: %s, name: %s)" % (author_email if author_email else "N/A", author_name if author_name else "N/A"))
                if args.allow_unkwnown_author:
                    print("        Continuing as user '%s' is allowed" % unknown_username)
                    new_unknown_data.append(x)
                else:
                    print("        Stopping as user '%s' is not allowed" % unknown_username)
                    exit(1)

            if author_login:
                x["author"] = author_login
                if not author_login in r:
                    r[author_login] = []
                r[author_login].append(x)

        if len(new_unknown_data) > 0:
            r[unknown_username] = new_unknown_data
        else:
            r.pop(unknown_username)

    return r

def get_top_contributors(r):
    if not r or not len(r.keys()) or not args.top_contributors:
        return None
    else:
        print("Calculating top contributors")
        max_contribs = []
        for k in r.keys():
            author_data = sort_results(r[k])
            author_contrib = {}
            author_contrib["author"] = k
            if "stats" in author_data and "difference" in author_data["stats"]:
                print("Author % s max contrib: %d" % (k, author_data["stats"]["difference"]))
                author_contrib["difference"] = author_data["stats"]["difference"]
            else:
                author_contrib["difference"] = 0
            max_contribs.append(author_contrib)
        max_contribs = sorted(max_contribs, key=lambda k: k['difference'], reverse=True)
        to_keep = max_contribs[:args.top_contributors]
        no_keep = max_contribs[args.top_contributors:]
        if to_keep:
            print("    Top contributors (in alphabetical order):\n        %s" % "\n        ".join(sorted([i["author"] for i in to_keep], key=str.lower)))
        #if no_keep:
        #    print("    Not Keeping:\n        %s" % "\n        ".join(sorted([i["author"] for i in no_keep], key=str.lower)))

        return [i["author"] for i in to_keep]

result = None
to_process = []
repos_html = []
csv_reader = csv.reader(open(args.file[0], newline=''), delimiter=',', quotechar='|')
for row in csv_reader:
    if len(row) < 9 or len(row) > 10:
        print ('wrong file format: %s (line: %s)' % (args.file[0], ",".join(row)))
        exit(1)
    repos_html.append("%s/%s" % (row[3], row[4]))
    to_process.append(row)

if len(to_process) == 0:
    print("No repository to process")
    exit(1)

print("Nb repos to process: %d\n" % len(to_process))

commits_to_ignore = []
commits_url_patterns = {}
for idx, row in enumerate(to_process, 1):
    # Commits to ignore.
    if len(row) == 9:
         commits_to_ignore.extend(row[8].split(commits_to_ignore_separator))
    owner = row[3]
    repo = row[4]
    commit_url_pattern = row[6]
    a = get_rep_stats(row[0], row[1], row[2], owner, repo, row[5], row[6], row[7], row[8], idx, len(to_process))
    if commit_url_pattern:
        commits_url_patterns["%s/%s" % (owner, repo)] = commit_url_pattern
    if a == None:
        exit(1)
    result = combine_results(result, a)

result = process_unknown(result)
result = remove_commits_to_ignore(result, commits_to_ignore)

# Sort and populate totals once all repos have been processed.
for x in result:
    a = result[x]
    #print (json.dumps(a, indent=4, sort_keys=True))
    a = sort_results(a)
    a = populate_totals(a)
    result[x] = a



#print (json.dumps(result, indent=4, sort_keys=True))

if result and len(result) > 0:
    output_filename = get_csv_output_filename_with_path()
    with open(output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        row = []
        row.append("Date")
        #row.append("Author")

        authors_pos = {}
        authors_hidden = {}

        top_contributors = get_top_contributors(result)

        html_data = {}

        for author in sorted(result.keys(), key=str.lower):
            if args.authors and author not in args.authors:
                authors_hidden[author] = 1
            elif not top_contributors or author in top_contributors:
                authors_pos[author] = len(authors_pos.keys()) + 1
                if args.output_commits:
                    row.append("%s (commits)" % author)
                    html_data["%s (commits)" % author] = {}
                    html_data["%s (commits)" % author]["data"] = []
                    html_data["%s (commits)" % author]["label"] = "%s (commits)" % author
                if args.output_additions:
                    row.append("%s (additions)" % author)
                    html_data["%s (additions)" % author] = {}
                    html_data["%s (additions)" % author]["data"] = []
                    html_data["%s (additions)" % author]["label"] = "%s (additions)" % author
                if args.output_deletions:
                    row.append("%s (deletions)" % author)
                    html_data["%s (deletions)" % author] = {}
                    html_data["%s (deletions)" % author]["data"] = []
                    html_data["%s (deletions)" % author]["label"] = "%s (deletions)" % author
                if args.output_differences:
                    row.append("%s (difference)" % author)
                    html_data["%s (difference)" % author] = {}
                    html_data["%s (difference)" % author]["data"] = []
                    html_data["%s (difference)" % author]["label"] = "%s (difference)" % author
                if args.output_totals:
                    row.append("%s (total)" % author)
                    html_data["%s (total)" % author] = {}
                    html_data["%s (total)" % author]["data"] = []
                    html_data["%s (total)" % author]["label"] = "%s (total)" % author
            else:
                authors_hidden[author] = 1



        # Add fictive 'Total' user to see general trend.
        nb_fields_per_author = 0
        if args.output_commits:
            row.append("%s (commits)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
            html_data["%s (commits)" % "TOTAL"] = {}
            html_data["%s (commits)" % "TOTAL"]["data"] = []
            html_data["%s (commits)" % "TOTAL"]["label"] = "%s (commits)" % "TOTAL"
        if args.output_additions:
            row.append("%s (additions)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
            html_data["%s (additions)" % "TOTAL"] = {}
            html_data["%s (additions)" % "TOTAL"]["data"] = []
            html_data["%s (additions)" % "TOTAL"]["label"] = "%s (additions)" % "TOTAL"
        if args.output_deletions:
            row.append("%s (deletions)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
            html_data["%s (deletions)" % "TOTAL"] = {}
            html_data["%s (deletions)" % "TOTAL"]["data"] = []
            html_data["%s (deletions)" % "TOTAL"]["label"] = "%s (deletions)" % "TOTAL"
        if args.output_differences:
            row.append("%s (difference)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
            html_data["%s (difference)" % "TOTAL"] = {}
            html_data["%s (difference)" % "TOTAL"]["data"] = []
            html_data["%s (difference)" % "TOTAL"]["label"] = "%s (difference)" % "TOTAL"
        if args.output_totals:
            row.append("%s (total)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
            html_data["%s (total)" % "TOTAL"] = {}
            html_data["%s (total)" % "TOTAL"]["data"] = []
            html_data["%s (total)" % "TOTAL"]["label"] = "%s (total)" % "TOTAL"

        row.append("Repository")
        row.append("Commit SHA")
        row.append("Commit URL")

        writer.writerow(row)

        total_nb_commits = 0
        total_additions = 0
        total_deletions = 0
        total_difference = 0
        total_total = 0

        for one_result in merge_results(result):
            the_author = one_result["author"]

            row = []
            the_date = datetime.datetime.strptime(one_result["date"], "%Y-%m-%dT%H:%M:%SZ")
            row.append(the_date.strftime(csv_date_format))
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
            html_object["sha"] = one_result["sha"]

            owner_repo = "%s/%s" % (one_result["owner"], one_result["repo"])
            commit_url = None
            if owner_repo in commits_url_patterns:
                commit_url = commits_url_patterns[owner_repo].replace("{{owner}}", one_result["owner"]).replace("{{repository}}", one_result["repo"]).replace("{{commit_sha}}", one_result["sha"])
                html_object["commit_url"] = commit_url


            if not the_author in authors_hidden and (not top_contributors or the_author in top_contributors):
                # Add empty cells to add in the right column.
                for x in range(0, authors_pos[the_author] - 1):
                    for y in range(0, nb_fields_per_author):
                        row.append("")

                #row.append(one_result["author"])
                #row.append(one_result["stats"]["additions"])
                #row.append(one_result["stats"]["deletions"])
                #row.append(one_result["stats"]["total"])
                if args.output_commits:
                    row.append(one_result["total_stats_author"]["nb_commits"])
                    h = copy.deepcopy(html_object)
                    h["y"] = one_result["total_stats_author"]["nb_commits"]
                    h["plus_minus"] = 1
                    html_data["%s (commits)" % the_author]["data"].append(h)
                if args.output_additions:
                    row.append(one_result["total_stats_author"]["additions"])
                    h = copy.deepcopy(html_object)
                    h["y"] = one_result["total_stats_author"]["additions"]
                    h["plus_minus"] = one_result["stats"]["additions"]
                    html_data["%s (additions)" % the_author]["data"].append(h)
                if args.output_deletions:
                    row.append(one_result["total_stats_author"]["deletions"])
                    h = copy.deepcopy(html_object)
                    h["y"] = one_result["total_stats_author"]["deletions"]
                    h["plus_minus"] = one_result["stats"]["deletions"]
                    html_data["%s (deletions)" % the_author]["data"].append(h)
                if args.output_differences:
                    row.append(one_result["total_stats_author"]["difference"])
                    h = copy.deepcopy(html_object)
                    h["y"] = one_result["total_stats_author"]["difference"]
                    h["plus_minus"] = one_result["stats"]["difference"]
                    html_data["%s (difference)" % the_author]["data"].append(h)
                if args.output_totals:
                    row.append(one_result["total_stats_author"]["total"])
                    h = copy.deepcopy(html_object)
                    h["y"] = one_result["total_stats_author"]["total"]
                    h["plus_minus"] = one_result["stats"]["total"]
                    html_data["%s (total)" % the_author]["data"].append(h)

                for x in range(authors_pos[the_author], len(authors_pos)):
                    for y in range(0, nb_fields_per_author):
                        row.append("")
            # We do not want to show users, still need to show totals, so fill
            # in all other users with empty stats.
            else:
                for x in range(0, len(authors_pos)):
                    for y in range(0, nb_fields_per_author):
                        row.append("")

            # Add fictive 'Total' user to see general trend.
            total_nb_commits = total_nb_commits + 1
            total_additions = total_additions + one_result["stats"]["additions"]
            total_deletions = total_deletions + one_result["stats"]["deletions"]
            total_difference = total_difference + one_result["stats"]["difference"]
            total_total = total_total + one_result["stats"]["total"]


            # This will only add the 'autor' to TOTAL since we create deep
            # copies of html_object.
            html_object["author"] = the_author;

            if args.output_commits:
                row.append(total_nb_commits)
                h = copy.deepcopy(html_object)
                h["y"] = total_nb_commits
                h["plus_minus"] = 1
                html_data["%s (commits)" % "TOTAL"]["data"].append(h)
            if args.output_additions:
                row.append(total_additions)
                h = copy.deepcopy(html_object)
                h["y"] = total_additions
                h["plus_minus"] = one_result["stats"]["additions"]
                html_data["%s (additions)" % "TOTAL"]["data"].append(h)
            if args.output_deletions:
                row.append(total_deletions)
                h = copy.deepcopy(html_object)
                h["y"] = total_deletions
                h["plus_minus"] = one_result["stats"]["deletions"]
                html_data["%s (deletions)" % "TOTAL"]["data"].append(h)
            if args.output_differences:
                row.append(total_difference)
                h = copy.deepcopy(html_object)
                h["y"] = total_difference
                h["plus_minus"] = one_result["stats"]["difference"]
                html_data["%s (difference)" % "TOTAL"]["data"].append(h)
            if args.output_totals:
                row.append(total_total)
                h = copy.deepcopy(html_object)
                h["y"] = total_total
                h["plus_minus"] = one_result["stats"]["total"]
                html_data["%s (total)" % "TOTAL"]["data"].append(h)

            # Show the repo this commit is comming from.
            row.append(owner_repo)
            row.append("%s" % one_result["sha"])
            if commit_url:
                row.append("%s" % commit_url)
                html_object["commit_url"] = commit_url
            else:
                row.append("")

            writer.writerow(row)

        print("Output file generated: %s" % output_filename)

        # Create the jinja2 environment.
        # Notice the use of trim_blocks, which greatly helps control whitespace.
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('chart.html')
        html_data_values = list(html_data.values())

        max_points_divide_factor = 1
        if args.max_points_html:
            total_nb_points = 0
            for hdv in html_data_values:
                for h in hdv["data"]:
                    total_nb_points = total_nb_points + len(h)
            if total_nb_points > args.max_points_html:
                max_points_divide_factor = int(total_nb_points / args.max_points_html)

        # Sort so that users appear in alphabetical order in the HTML.
        total_values = html_data_values[-nb_fields_per_author:]
        total_values = sorted(total_values, key=lambda k: k['label'].lower(), reverse=False)
        html_data_values = html_data_values[:-nb_fields_per_author]
        html_data_values = sorted(html_data_values, key=lambda k: k['label'].lower(), reverse=False)
        # We want TOTAL to appear last.
        html_data_values.extend(total_values)

        output_from_parsed_template = template.render(labels_and_data=html_data_values,
                                                      generation_date=now.strftime(csv_date_format),
                                                      repositories=sorted(repos_html, key=str.lower),
                                                      authors_hidden=sorted(authors_hidden.keys(), key=str.lower),
                                                      max_points_divide_factor=max_points_divide_factor,
                                                      title=get_html_title())

        # to save the results
        html_output_filename = get_html_output_filename_with_path()
        with open(html_output_filename, "w") as fh:
            fh.write(output_from_parsed_template)

        print("Output file generated: %s" % html_output_filename)

        print("    Total nb authors: %d" % (len(authors_hidden.keys()) + len(authors_pos.keys())))
        if len(authors_hidden.keys()) > 0:
            print("    Stats for the following authors are not included:\n        %s" % "\n        ".join(sorted(authors_hidden.keys(), key=str.lower)))

exit_code = 0
print ('\nDone.')
exit(exit_code)
