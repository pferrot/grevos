'''
Usage:
Just run with the necessary arguments (-h for details).
'''
import json
import argparse
import re
import csv
import datetime

from requests import get



parser = argparse.ArgumentParser(description='Collect contributors statistics on specified GitHub repositories.')
parser.add_argument('-t', '--tokens', type=str, nargs='+', help='valid API token for retrieving files from git.autodesk.com')
parser.add_argument('-r', '--repositories', type=str, nargs='+', help='full URLs of all repositories')

args = parser.parse_args()
if not args.tokens:
    print ('git_token not specified (use -h for details)')
    exit(1)
if not args.repositories:
    print ('gitcontractors_token not specified (use -h for details)')
    exit(1)

direct_dependencies_cache = {}
recursive_dependencies_cache = {}


epoch = datetime.datetime.utcfromtimestamp(0)

def unix_time_millis(dt):
    return (dt - epoch).total_seconds() * 1000

def get_commit_details(scheme, host, owner, repo, commit_sha, git_token):
    url = "%s%s/repos/%s/%s/commits/%s" % (scheme, host, owner, repo, commit_sha)
    #print (url)
    headers = \
        {
         'Authorization': 'token %s' % git_token
        }
    reply = get(url, headers=headers)
    code = reply.status_code
    if code == 200:
        out = reply.content
        js = json.loads(out.decode('utf-8'))
        #print (json.dumps(js, indent=4, sort_keys=True))
        commit_date = None
        if "commit" in js and "author" in js["commit"] and "date" in js["commit"]["author"]:
            commit_date = js["commit"]["author"]["date"]
        else:
            print ("Could not find commit date in \n\n%s" % json.dumps(js, indent=4, sort_keys=True))

        result = {}
        result["stats"] = js["stats"]
        # Let track the difference as it may be what is most meaningful to measure.
        result["stats"]["difference"] = result["stats"]["additions"] - result["stats"]["deletions"]
        result["date"] = commit_date
        return result
    else:
        print ("Erreur retrieving commit (status code: %d) at %s" % (status_code, url))
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

# Show the version of CI dependencies, see https://git.autodesk.com/LocalizationServices/sbt-ci-helper
# for more info.
def get_rep_stats(scheme, host, owner, repo, branch, since, git_token):
    # URL looks like https://git.autodesk.com/api/v3/repos/LocalizationServices/segs-app/contents/ciHelperDepOverrides.sbt?ref=0.1-SEGSF-320-8928289eb0-20171114022552PST
    url = "%s%s/repos/%s/%s/commits?sha=%s%s" % (scheme, host, owner, repo, branch, "&since=%s" % since if since else "")
    #print (url)
    headers = \
        {
         'Authorization': 'token %s' % git_token
        }
    reply = get(url, headers=headers)
    code = reply.status_code
    result = {}
    if code == 200:
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

            one_result = {}
            if author_login:
                print ("Author: %s" % author_login)
            else:
                print ("Author could not be found in: \n\n%s" % json.dumps(one_js, indent=4, sort_keys=True))
                author_login = "unknown"
            one_result["author"] = author_login
            if commit_sha:
                print ("SHA: %s" % commit_sha)
                one_result["sha"] = commit_sha
                commit_details = get_commit_details(scheme, host, owner, repo, commit_sha, git_token)
                if commit_details:
                    print ("Date: %s" % commit_details["date"])
                    print ("Additions: %s" % commit_details["stats"]["additions"])
                    print ("Deletions: %s" % commit_details["stats"]["deletions"])
                    print ("Difference: %s" % commit_details["stats"]["difference"])
                    print ("Total: %s" % commit_details["stats"]["total"])

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
                print ("Commit SHA could not be found in: \n\n%s" % json.dumps(one_js, indent=4, sort_keys=True))

        for x in result:
            a = result[x]
            #print (json.dumps(a, indent=4, sort_keys=True))
            a = sorted(a, key=lambda k: k['date_unix'], reverse=False)
            a = populate_totals(a)
            result[x] = a
        return result
    else:
        print ("Erreur retrieving commits (status code: %d) at %s" % (status_code, url))
        return None


def merge_results(r):
    result = []
    for x in r.keys():
        print ("X: %s" % x)
        print (json.dumps(r[x], indent=4, sort_keys=True))
        result.extend(r[x])
    return sorted(result, key=lambda k: k['date_unix'], reverse=False)




result = get_rep_stats('https://', 'api.github.com', 'pferrot', 'ochothon', 'master', '2015-11-01T00:00:00Z', 'XXXXXXX')




print (json.dumps(result, indent=4, sort_keys=True))

if result and len(result) > 0:
    with open('test.csv', 'w', newline='') as csvfile:
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
