# GREVOS
GREVOS is a simple Python command line tool for generating graphs showing the **combined** activity of any number of GitHub repositories.

GitHub activity graphs are nice, but large projects are often composed of more than one single git repository. GREVOS generates activity graphs for any number of repositories, thus allowing to see the pace of the entire project and who contributes.

## Features
* HTML and CSV outputs.
* Available statistics:
  * Number of commits
  * Additions
  * Deletions
  * Difference (= additions - deletions)
  * Total (= additions + deletions)
* All statistics can be enabled/disabled in the generated output.
* HTML output features:
  * Nice chart showing the progress of your projects.
  * Show total as well as per user contributions.
  * Access commit details on github.com by clicking a point in the graph.
* CSV output features:
  * Specify your preferred date format.
  * Show total as well as per user contributions.
  * Format makes it trivial to generate graph in Excel.
* Possibility to filter by user if you are only interested in the stats for a few users.
* Possibility to keep top contributors only.
* Possibility to map unknown authors to a given username when only email or name is available (but no login name).
* Possibility to limit commits to take into account based on the number of lines added - removed. Convenient to exclude commits that would otherwise bias the statistics (e.g when code formatting is applied or large files are copied into the project).
* Possibility to define `since` date. Convenient when working with very large repositories that contain a large number of commits over the years.
* Works with GitHub API. No need to clone the repositories locally.
* Cache mechanism to not have to fetch data from GitHub every time.
* Works with GitHub Enterprise.

## Prerequisites
* Python 3 (tested with 3.6.5)
* Following libraries must be available (install with pip3 for example):
  * requests
  * jinja2

## Usage
```
Patrices-MacBook-Air:grevos patrice$ python3 grevos.py -h
GREVOS
------

usage: grevos.py [-h] [-f FILE] [-a [AUTHORS [AUTHORS ...]]]
                 [-o [OUTPUT_FOLDER]] [-c [CACHE_FOLDER]]
                 [-oc [OUTPUT_COMMITS]] [-oa [OUTPUT_ADDITIONS]]
                 [-od [OUTPUT_DELETIONS]] [-odi [OUTPUT_DIFFERENCES]]
                 [-ot [OUTPUT_TOTALS]] [-d [CSV_DATE_FORMAT]]
                 [-eaf [EMAIL_TO_AUTHOR_FILE]] [-naf [NAME_TO_AUTHOR_FILE]]
                 [-macd [MAX_COMMIT_DIFFERENCE]]
                 [-micd [MIN_COMMIT_DIFFERENCE]] [-tc [TOP_CONTRIBUTORS]]
                 [-mph [MAX_POINTS_HTML]]

Generate combined activity graphs for any number of repositories.

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  File containing the repos to process. Format: <scheme>
                        ,<host>,<base_path>,<org>,<repo>,<branch>,<commit_url_
                        pattern>,<since>,<api_token>[,<commits_to_ignore>].
                        <commits_to_ignore> is a - separated list of SHA
                        commits.
  -a [AUTHORS [AUTHORS ...]], --authors [AUTHORS [AUTHORS ...]]
                        Only outputs statistics for the specified authors (all
                        authors by default).
  -o [OUTPUT_FOLDER], --output_folder [OUTPUT_FOLDER]
                        Folder where the generated CSV files are stored,
                        default: 'output'.
  -c [CACHE_FOLDER], --cache_folder [CACHE_FOLDER]
                        Folder where cache files are stored, default: 'cache'.
  -oc [OUTPUT_COMMITS], --output_commits [OUTPUT_COMMITS]
                        Outputs nb commits in genereted files, default: yes.
  -oa [OUTPUT_ADDITIONS], --output_additions [OUTPUT_ADDITIONS]
                        Outputs additions in genereted files, default: yes.
  -od [OUTPUT_DELETIONS], --output_deletions [OUTPUT_DELETIONS]
                        Outputs deletions in genereted files, default: yes.
  -odi [OUTPUT_DIFFERENCES], --output_differences [OUTPUT_DIFFERENCES]
                        Outputs differences (i.e. additions - deletions) in
                        genereted files, default: yes.
  -ot [OUTPUT_TOTALS], --output_totals [OUTPUT_TOTALS]
                        Outputs totals (i.e. additions + deletions) in
                        genereted files, default: yes.
  -d [CSV_DATE_FORMAT], --csv_date_format [CSV_DATE_FORMAT]
                        Date format in the generated CSV, default: '%m/%d/%Y
                        %H:%M:%S'.
  -eaf [EMAIL_TO_AUTHOR_FILE], --email_to_author_file [EMAIL_TO_AUTHOR_FILE]
                        File providing the mapping between email and username,
                        useful when the username is not available in the Git
                        commit but the email is. File format: one entry per
                        line, first item is the email, second item is the
                        username, separated by a comma.
  -naf [NAME_TO_AUTHOR_FILE], --name_to_author_file [NAME_TO_AUTHOR_FILE]
                        File providing the mapping between name and username,
                        useful when the username is not available in the Git
                        commit but the name is. File format: one entry per
                        line, first item is the name, second item is the
                        username, separated by a comma.
  -macd [MAX_COMMIT_DIFFERENCE], --max_commit_difference [MAX_COMMIT_DIFFERENCE]
                        Max difference of a commit (i.e. additions -
                        deletions) for it to be considered, default: no limit.
                        This is useful to exclude commits that do not make
                        sense to take into account because many files were
                        copied into the repository (e.g. JavaScript files in
                        node.js projects).
  -micd [MIN_COMMIT_DIFFERENCE], --min_commit_difference [MIN_COMMIT_DIFFERENCE]
                        Min difference of a commit (i.e. additions -
                        deletions) for it to be considered, default: no limit.
                        This is useful to exclude commits that do not make
                        sense to take into account because many files were
                        removed from the repository (e.g. JavaScript files in
                        node.js projects).
  -tc [TOP_CONTRIBUTORS], --top_contributors [TOP_CONTRIBUTORS]
                        Only keep the n top contributors based on the number
                        of (additions - deletions), default: keep all.
  -mph [MAX_POINTS_HTML], --max_points_html [MAX_POINTS_HTML]
                        Maximum number of points in the HTML output. A graph
                        with too many points will not offer a good user
                        experience.
```

## Example

Source file listing the repositories, `drupal.csv` (`XXXXXXXXXXXXXXXXXXXXX` must be replaced with [your own personal API token](https://blog.github.com/2013-05-16-personal-api-tokens/)):
```
https://,api.github.com,,drupal,drupal,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-datetime,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-utility,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-proxy-builder,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-class-finder,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-assertion,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-uuid,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-transliteration,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-plugin,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-serialization,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-http-foundation,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-render,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-filesystem,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-file-cache,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-event-dispatcher,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-discovery,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-php-storage,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-graph,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
https://,api.github.com,,drupal,core-annotation,8.6.x,https://github.com/{{owner}}/{{repository}}/commit/{{commit_sha}},2017-01-01T00:00:00Z,XXXXXXXXXXXXXXXXXXXXX
```

Then run with the desired parameters, e.g.:

```
python3 grevos.py \
-oc yes -oa yes -od yes -odi yes -ot yes \
-tc 5 -macd 5000 -micd -5000 -mph 500 \
-f drupal.csv
```

And then wait until all commits have been processed. Note that the first time you generate a graph for a given repository, it might take some time as the data must be retrieved from GitHub. Supsequent executions will be much faster thanks to the necessary data being cached locally.
```
Patrices-MacBook-Air:grevos patrice$ python3 grevos.py -oc yes -oa yes -od yes -odi yes -ot yes -tc 4 -macd 5000 -micd -5000 -mph 500 -f drupal.csv
GREVOS
------

Source file: drupal.csv
Output folder: output
Cache folder: cache
Nb repos to process: 20

Processing: https://api.github.com/repos/drupal/drupal/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 1 / 20)
    Cache found (file: cache/b70765d0068a2bb13d83cce40a63d074d082bc17)
    Recovered 2159 commits from cache
    Done processing commits (total nb commits processed: 2159)
Processing: https://api.github.com/repos/drupal/core/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 2 / 20)
    Cache found (file: cache/99c51b29f3eeb734679d4920c018c6d1d65651da)
    Recovered 2125 commits from cache
    Done processing commits (total nb commits processed: 2125)
Processing: https://api.github.com/repos/drupal/core-datetime/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 3 / 20)
    Cache found (file: cache/17762de885c7f97637336024863ecf94f908a8f7)
    Recovered 19 commits from cache
    Done processing commits (total nb commits processed: 19)
Processing: https://api.github.com/repos/drupal/core-utility/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 4 / 20)
    Cache found (file: cache/0d819a0b0ad72c7f43056820b6f0f3831197fd2c)
    Recovered 24 commits from cache
    Done processing commits (total nb commits processed: 24)
Processing: https://api.github.com/repos/drupal/core-proxy-builder/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 5 / 20)
    Cache found (file: cache/6cd253a2d67f6fc36620929b2fe4fadd75e9478a)
    Recovered 1 commits from cache
    Done processing commits (total nb commits processed: 1)
Processing: https://api.github.com/repos/drupal/core-class-finder/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 6 / 20)
    Cache found (file: cache/401c8d06e61e4af48405a96fab42d93130f2b922)
    Recovered 2 commits from cache
    Done processing commits (total nb commits processed: 2)
Processing: https://api.github.com/repos/drupal/core-assertion/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 7 / 20)
    Cache found (file: cache/76f53502da589622b10ae073f7cc910bf7a0bcd8)
    Recovered 4 commits from cache
    Done processing commits (total nb commits processed: 4)
Processing: https://api.github.com/repos/drupal/core-uuid/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 8 / 20)
    Cache found (file: cache/3cb534470d80d4ec9f62cb63e7d6f9071d0c085d)
    Recovered 4 commits from cache
    Done processing commits (total nb commits processed: 4)
Processing: https://api.github.com/repos/drupal/core-transliteration/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 9 / 20)
    Cache found (file: cache/23329bcb4a7d0fe10a7a85bb22b370a6bb1572fb)
    Recovered 4 commits from cache
    Done processing commits (total nb commits processed: 4)
Processing: https://api.github.com/repos/drupal/core-plugin/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 10 / 20)
    Cache found (file: cache/b456d82119a410409b72e8d4300ab864fa436360)
    Recovered 15 commits from cache
    Done processing commits (total nb commits processed: 15)
Processing: https://api.github.com/repos/drupal/core-serialization/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 11 / 20)
    Cache found (file: cache/49ee06b9a5a8f5d945fc152f95fb5a5146810758)
    Recovered 11 commits from cache
    Done processing commits (total nb commits processed: 11)
Processing: https://api.github.com/repos/drupal/core-http-foundation/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 12 / 20)
    Cache found (file: cache/079fe0f862a89ca5921c8d5a5dcbe5dbfaa89523)
    Recovered 6 commits from cache
    Done processing commits (total nb commits processed: 6)
Processing: https://api.github.com/repos/drupal/core-render/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 13 / 20)
    Cache found (file: cache/e2f4dae8d9884c213696ab826fce61c74a4f88ff)
    Recovered 6 commits from cache
    Done processing commits (total nb commits processed: 6)
Processing: https://api.github.com/repos/drupal/core-filesystem/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 14 / 20)
    Cache found (file: cache/f47d2771f7778441f5a0afac234b0f142cd051c7)
    Recovered 2 commits from cache
    Done processing commits (total nb commits processed: 2)
Processing: https://api.github.com/repos/drupal/core-file-cache/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 15 / 20)
    Cache found (file: cache/a9995027d7b73c71a8f1da20041ea7aec0090f4a)
    Recovered 2 commits from cache
    Done processing commits (total nb commits processed: 2)
Processing: https://api.github.com/repos/drupal/core-event-dispatcher/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 16 / 20)
    Cache found (file: cache/1168c7a2e4091c4254fc5c9887953e13aac8702f)
    Recovered 8 commits from cache
    Done processing commits (total nb commits processed: 8)
Processing: https://api.github.com/repos/drupal/core-discovery/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 17 / 20)
    Cache found (file: cache/b9eed3128f9e7363f1d9bb7fd8ae038e88fbc254)
    Recovered 6 commits from cache
    Done processing commits (total nb commits processed: 6)
Processing: https://api.github.com/repos/drupal/core-php-storage/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 18 / 20)
    Cache found (file: cache/9c7e506c24da9129489d16c7055244355ee10b69)
    Recovered 7 commits from cache
    Done processing commits (total nb commits processed: 7)
Processing: https://api.github.com/repos/drupal/core-graph/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 19 / 20)
    Cache found (file: cache/4ecba3df3ddedee008f25c5ece4bb54e50a5a534)
    Recovered 2 commits from cache
    Done processing commits (total nb commits processed: 2)
Processing: https://api.github.com/repos/drupal/core-annotation/commits?sha=8.6.x&since=2017-01-01T00:00:00Z (repo 20 / 20)
    Cache found (file: cache/61fe85bba4b2879c590e56c7f94731dbad017e85)
    Recovered 10 commits from cache
    Done processing commits (total nb commits processed: 10)
Processing '<unknown>' user data
Removing commits to ignore
    Removing commit because it is above the max difference limit in drupal/drupal: 8287017e034bc323dec1d86b3f37a804aa082d2d (16060)
    Removing commit because it is above the max difference limit in drupal/core: 3be4bb20203d42a0f4e30b2334ae017d112e20e0 (16060)
    Removing commit because it is above the max difference limit in drupal/drupal: 88a22ddacc302bd1fe2397c8441d85f8b59f4b33 (5559)
    Removing commit because it is above the max difference limit in drupal/core: 835361c2b0f17cc53fd0a63f57b6689bb19dbfa3 (5559)
    Removing commit because it is above the max difference limit in drupal/drupal: f7c9dd9352350a05667208fdd79f3eff1b86e9e8 (5093)
    Removing commit because it is below the min difference limit in drupal/drupal: 08d676a2ecb2db5da4f09e7701b04381f2e50e05 (-5559)
    Removing commit because it is above the max difference limit in drupal/core: e36b6a7db72b1086b0513819ce8b18a3a081a2d2 (5093)
    Removing commit because it is below the min difference limit in drupal/core: d2371e645e370e85869e990290f8158fb39c6aee (-5559)
    Removing commit because it is above the max difference limit in drupal/drupal: aead8ca4089e716c70cd95c9e3460e683e524774 (10699)
    Removing commit because it is above the max difference limit in drupal/core: 009d4839835a494e6775c8817d44b9b8d566e458 (10699)
    Removing commit because it is below the min difference limit in drupal/drupal: e05bab84bb42b3ccaaa0f34b12486164d1310a1f (-5076)
    Removing commit because it is above the max difference limit in drupal/drupal: 01621e5880b7e0efd335cb0bae243c25fc3b1c2e (6419)
    Removing commit because it is below the min difference limit in drupal/core: 0f7b533e45d325d46cb431e696a02e836dff0a93 (-5076)
    Removing commit because it is above the max difference limit in drupal/core: dec21e4aa92942bcc630059a61f8161c794c84ad (6419)
Calculating top contributors
    Author alexpott contrib: 80920
    Author larowlan contrib: 68910
    Author xjm contrib: 6179
    Author goba contrib: 16544
    Author effulgentsia contrib: 24081
    Author webchick contrib: 11976
    Author cilefen contrib: 4051
    Author dbuytaert contrib: -8
    Author Nathaniel Catchpole contrib: 107790
    Author Francesco Placella contrib: -532
    Author Lauri Eskola contrib: 4329
    Author Roy Scholten contrib: -4
    Author Scott Reeves contrib: 228
    Top contributors (in alphabetical order):
        alexpott
        effulgentsia
        larowlan
        Nathaniel Catchpole
Replacing authors to hide with OTHERS
    Replaced 9 author(s)
Output file generated: output/drupal_20180412121215.csv
Output file generated: output/drupal_20180412121215.html
    Total nb authors: 15
    OTHERS include the following authors:
        cilefen
        dbuytaert
        Francesco Placella
        goba
        Lauri Eskola
        Roy Scholten
        Scott Reeves
        webchick
        xjm

Done.
```

You can have a look at the generated files in the [docs](docs) folder.
You can even play with the generated HTML <a href="http://patriceferrot.com/grevos/drupal_20180412121215.html">here</a> (screenshot below).

<a href="http://patriceferrot.com/grevos/drupal_20180412121215.html"><img src="docs/drupal.png"/></a>
