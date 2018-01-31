# Is It Up?

Checks a series of TCP services listed in a SQLite database to see if they are
up or down. If a successful TCP connection is made, the associated URL is
retrieved, signifying to a remote tracking service such as healthchecks.io that
the TCP service is up.

Where this is superior to a simple
`tcpclient -HR hostname port echo && wget https://url -q` is that it implements
retries. If a host cannot be contacted within the default 30 minutes since it
was last up, it will be retried once per minute until it responds. This can be
throttled down by tweaking the crontab entry to match your grace period for your
tracking service. For instance, most of my entries are set to update every 30
minutes with a 10 minute grace period. My crontab entry might look something
like `0-10,30-40 * * * * python isitup.py --check` (full paths omitted for
brevity). If a host has shown to be up within the check time (default 30 min)
then it will be ignored for future checks, so we aren't hammering all of the
behaving hosts once a minute, 20 minutes out of every hour. We only continue to
check the ones that have failed to respond to the previous attempt.

## Usage

```
usage: isitup.py [-h] | [--check] [--verbose] | [--list]
                 [--remove-check REMOVE_CHECK]
                 [--add-check] [--host HOST] [--port PORT] [--url URL]

optional arguments:
  -h, --help            show this help message and exit
  --check               Run the availability check
  --verbose             Display information while running
  --list                List the checks in the database
  --remove-check REMOVE_CHECK
                        Remove the specified check from the database

  --add-check           Add a check to the database
  --host HOST           The hostname of the entry to add
  --port PORT           The port of the entry to add
  --url URL             The URL of the entry to add
```

There are four modes that IsItUp can be run under, each is exclusive of the
other. Selecting one will mean you will not be allowed to select another.

The first is the basic `--help` which will display the usage information, much
like is shown above.

Next is the `--check` option, which will run a check and see if anything of the
hosts need to be contacted yet. The `--verbose` option adds output information
to this mode, otherwise nothing is displayed (perfect for running via `cron`).

Then we have `--list` which will display a list of all of the checks in the
database. You will need to note the ID number in brackets if you intend to
delete a check from the database.

That brings us to `--remove-check`, which will remove the numbered check from
the database. As stated previously, you'll need to know the number from the
output of `--list`.

Lastly is `--add-check` where we can add new checks to the database. It must be
used in conjunction with the `--host <HOST>` `--port <PORT>`, and `--url <URL>`
options.

## TODO:

 - [ ] Rewrite this doc
