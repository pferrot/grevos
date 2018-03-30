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

from requests import get



parser = argparse.ArgumentParser(description='Collect contributors statistics on specified GitHub repositories.')
parser.add_argument('-f', '--file', type=str, nargs=1, help='file containing the repos to process')
parser.add_argument('-i', '--ignore_files', type=str, nargs='*', help='ignore commits with one of those files added')

args = parser.parse_args()
print
if not args.file:
    print ('file not specified (use -h for details)')
    exit(1)
elif not os.path.exists(args.file[0]):
    print ('file does not exist: %s' % args.file[0])
    exit(1)

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


def get_rep_stats(scheme, host, base_path, owner, repo, branch, since, git_token, index_repo, total_nb_repos):
    next_url = "%s%s%s/repos/%s/%s/commits?sha=%s%s (%s)" % (scheme, host, base_path, owner, repo, branch, "&since=%s" % since if since else "", "repo %d / %d" % (index_repo, total_nb_repos))
    print ("Processing: %s" % next_url)
    counter = 0
    result = {}
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
                counter = counter + 1
                author_email = None
                commit_sha = None
                #print (json.dumps(one_js, indent=4, sort_keys=True))
                if "author" in one_js and one_js["author"] and "login" in one_js["author"]:
                    author_login = one_js["author"]["login"]
                if "sha" in one_js:
                    commit_sha = one_js["sha"]

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

                if (counter % 20 == 0):
                    print ("    Nb commits processed so far: %d (last date: %s)" % (counter, one_result['date_formatted']))

        else:
            print ("    Erreur retrieving commits (status code: %d) at %s" % (status_code, next_url))
            return None

    print ("    Done processing commits (total nb commits processed: %d)" % counter)
    return result


def merge_results(r):
    result = []
    for x in r.keys():
        #print ("X: %s" % x)
        #print (json.dumps(r[x], indent=4, sort_keys=True))
        result.extend(r[x])
    return sorted(result, key=lambda k: k['date_unix'], reverse=False)

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
    a = sorted(a, key=lambda k: k['date_unix'], reverse=False)
    a = populate_totals(a)
    result[x] = a

#print (json.dumps(result, indent=4, sort_keys=True))

if result and len(result) > 0:
    with open('contributors_stats_%s.csv' % datetime.datetime.now().strftime("%Y%m%d%H%M%S"), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        row = []
        row.append("Date")
        #row.append("Author")


        authors_pos = {}
        for author in result.keys():
            authors_pos[author] = len(authors_pos.keys()) + 1

            row.append("Commits (%s)" % author)
            row.append("Additions (%s)" % author)
            row.append("Deletions (%s)" % author)
            row.append("Difference (%s)" % author)
            row.append("Total (%s)" % author)

        writer.writerow(row)

        nb_fields_per_author = 5

        for one_result in merge_results(result):
            the_author = one_result["author"]

            row = []
            row.append(one_result["date_formatted"])

            # Add empty cells to add in the right column.
            for x in range(0, authors_pos[the_author] - 1):
                for y in range(0, nb_fields_per_author):
                    row.append("")


            #row.append(one_result["author"])
            #row.append(one_result["stats"]["additions"])
            #row.append(one_result["stats"]["deletions"])
            #row.append(one_result["stats"]["total"])
            row.append(one_result["total_stats_author"]["nb_commits"])
            row.append(one_result["total_stats_author"]["additions"])
            row.append(one_result["total_stats_author"]["deletions"])
            row.append(one_result["total_stats_author"]["difference"])
            row.append(one_result["total_stats_author"]["total"])

            writer.writerow(row)

exit_code = 0
print ('\nDone.')
exit(exit_code)
