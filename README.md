# Is It Up?

Checks a series of TCP services listed in a SQLite database to see if they are
up or down. If a successful TCP connection is made, the associated URL is
retrieved, signifying to a remote tracking service such as healthchecks.io that
the TCP service is up.

Where this is superior to a simple
`tcpclient -HR hostname port echo @@ wget https://url -q` is that it implements
retries. If a host cannot be contacted within the default 30 minutes since it
was last up, it will be retried once per minute until it responds. This can be
throttled down by tweaking the crontab entry to match your grace period for your
tracking service. For instance, most of my entries are set to update every 30
minutes with a 10 minute grace period. My crontab entry might look something
like `0-10,30-40 * * * * python IsItUp.py --check` (full paths omitted for
brevity). If a host has shown to be up within the check time (default 30 min)
then it will be ignored for future checks, so we aren't hammering all of they
behaving hosts once a minute, 20 minutes out of every hour, only the ones that
have failed to respond to the previous attempt.

## TODO:

 - [ ] Implement HTTP URL retrieval when a host is up
 - [ ] Rewrite this doc
 
