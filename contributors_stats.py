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

from requests import get

# Need to be manually updated. Should allow to prevent using old JSON cache
# when the schema has been modified with a new version.
schema_version = 1
cache_folder = 'cache'
output_folder = 'output'
csv_additions = True
csv_deletions = True
csv_differences = True
csv_totals = True
csv_commits = True

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

parser = argparse.ArgumentParser(description='Collect contributors statistics on specified GitHub repositories.')
parser.add_argument('-f', '--file', type=str, nargs=1, help='file containing the repos to process')
parser.add_argument('-i', '--ignore_files', type=str, nargs='*', help='ignore commits with one of those files added')
parser.add_argument('-a', '--authors', type=str, nargs='*', help='only outputs statistics for the specified authors (all authors by default)')
parser.add_argument('-o', '--output_folder', type=str, nargs='?', help='folder where the generated CSV files are stored, default: \'%s\'' % output_folder)
parser.add_argument('-c', '--cache_folder', type=str, nargs='?', help='folder where cache files are stored, default: \'%s\'' % cache_folder)
parser.add_argument('-cc', '--csv_commits', type=str2bool, nargs='?', default=True, help='outputs nb commits in genereted CSV, default: yes')
parser.add_argument('-ca', '--csv_additions', type=str2bool, nargs='?', default=True, help='outputs additions in genereted CSV, default: yes')
parser.add_argument('-cd', '--csv_deletions', type=str2bool, nargs='?', default=True, help='outputs deletions in genereted CSV, default: yes')
parser.add_argument('-cdi', '--csv_differences', type=str2bool, nargs='?', default=True, help='outputs differences (i.e. additions - deletions) in genereted CSV, default: yes')
parser.add_argument('-ct', '--csv_totals', type=str2bool, nargs='?', default=True, help='outputs totals (i.e. additions + deletions) in genereted CSV, default: yes')

args = parser.parse_args()

print("CSV commits: %s " % args.csv_commits)

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

print ("Output folder: %s" % output_folder)
print ("Cache folder: %s" % cache_folder)


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

def get_output_filename():
    base_name = os.path.basename(args.file[0])
    if base_name.find('.') > 0:
        base_name = base_name[:base_name.find('.')]
    return '%s_%s.csv' % (base_name, datetime.datetime.now().strftime("%Y%m%d%H%M%S"))

def get_output_filename_with_path():
    return get_filename_with_path(get_output_filename(), output_folder)

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
        return None
    else:
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




def get_rep_stats(scheme, host, base_path, owner, repo, branch, since, git_token, index_repo, total_nb_repos):
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

                if not author_login:
                    print ("    Author could not be found in: \n\n%s" % json.dumps(one_js, indent=4, sort_keys=True))
                    author_login = "unknown"
                #else:
                #    print ("Author: %s" % author_login)
                one_result["author"] = author_login
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
                            one_result['date_formatted'] = d.strftime('%d.%m.%Y %H:%M:%S')
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
                    print ("    Nb commits processed so far: %d (last date: %s)" % (counter, one_result['date_formatted']))

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


result = None
to_process = []
csv_reader = csv.reader(open(args.file[0], newline=''), delimiter=',', quotechar='|')
for row in csv_reader:
    to_process.append(row)

if len(to_process) == 0:
    print("No repository to process")
    exit(1)

print("Nb repos to process: %d" % len(to_process))

for idx, row in enumerate(to_process, 1):
    a = get_rep_stats(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], idx, len(to_process))
    if a == None:
        exit(1)
    result = combine_results(result, a)


# Sort and populate totals once all repos have been processed.
for x in result:
    a = result[x]
    #print (json.dumps(a, indent=4, sort_keys=True))
    a = sort_results(a)
    a = populate_totals(a)
    result[x] = a



#print (json.dumps(result, indent=4, sort_keys=True))

if result and len(result) > 0:
    output_filename = get_output_filename_with_path()
    with open(output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        row = []
        row.append("Date")
        #row.append("Author")


        authors_pos = {}
        for author in result.keys():
            if not args.authors or author in args.authors:
                authors_pos[author] = len(authors_pos.keys()) + 1
                if args.csv_commits:
                    row.append("%s (commits)" % author)
                if args.csv_additions:
                    row.append("%s (additions)" % author)
                if args.csv_deletions:
                    row.append("%s (deletions)" % author)
                if args.csv_differences:
                    row.append("%s (difference)" % author)
                if args.csv_totals:
                    row.append("%s (total)" % author)

        # Add fictive 'Total' user to see general trend.
        nb_fields_per_author = 0
        if args.csv_commits:
            row.append("%s (commits)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
        if args.csv_additions:
            row.append("%s (additions)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
        if args.csv_deletions:
            row.append("%s (deletions)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
        if args.csv_differences:
            row.append("%s (difference)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1
        if args.csv_totals:
            row.append("%s (total)" % "TOTAL")
            nb_fields_per_author = nb_fields_per_author + 1

        writer.writerow(row)

        total_nb_commits = 0
        total_additions = 0
        total_deletions = 0
        total_difference = 0
        total_total = 0
        for one_result in merge_results(result):
            the_author = one_result["author"]

            row = []
            row.append(one_result["date_formatted"])

            if not args.authors or author in args.authors:

                # Add empty cells to add in the right column.
                for x in range(0, authors_pos[the_author] - 1):
                    for y in range(0, nb_fields_per_author):
                        row.append("")

                #row.append(one_result["author"])
                #row.append(one_result["stats"]["additions"])
                #row.append(one_result["stats"]["deletions"])
                #row.append(one_result["stats"]["total"])
                if args.csv_commits:
                    row.append(one_result["total_stats_author"]["nb_commits"])
                if args.csv_additions:
                    row.append(one_result["total_stats_author"]["additions"])
                if args.csv_deletions:
                    row.append(one_result["total_stats_author"]["deletions"])
                if args.csv_differences:
                    row.append(one_result["total_stats_author"]["difference"])
                if args.csv_totals:
                    row.append(one_result["total_stats_author"]["total"])

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

            if args.csv_commits:
                row.append(total_nb_commits)
            if args.csv_additions:
                row.append(total_additions)
            if args.csv_deletions:
                row.append(total_deletions)
            if args.csv_differences:
                row.append(total_difference)
            if args.csv_totals:
                row.append(total_total)

            writer.writerow(row)

        print("Output file generated: %s" % output_filename)

exit_code = 0
print ('\nDone.')
exit(exit_code)
