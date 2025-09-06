"""
Generate synthetic training data for finetuning:
- pairs.jsonl: {"input": <raw transcript>, "output": <strict JSON>}
- trl_messages.jsonl: {"messages": [developer, user, assistant]}

The schema for the JSON output:
{
  "summary": str,
  "key_successes": [{"desc": str, "specifics": str, "adjacent_context": str}, ...],
  "blockers": [{"desc": str, "impact": str, "owner_hint": str, "resolution_hint": str}, ...],
  "resources": [str, ...]
}
"""

import json
import random
import textwrap
import datetime
import os
import re
from pathlib import Path

random.seed(7)

SCHEMA_TEXT = textwrap.dedent("""\
Schema:
[
  {
    "summary": "High-level overview of what happened in this session",
    "key_successes": [
      {
        "desc": "Short description of a concrete success",
        "specifics": "Command(s) or evidence from the transcript",
        "adjacent_context": "Any context like counts, times, branch names"
      }
    ],
    "blockers": [
      {
        "desc": "Problem described succinctly",
        "impact": "What this blocks or risks",
        "owner_hint": "Likely owner or team",
        "resolution_hint": "First debugging direction"
      }
    ],
    "resources": ["Short actionable resources or next steps"]
  }
]
""")

def esc(s):
    """Sprinkle some ANSI/OSC noise to simulate 'script' logs"""
    noise = [
        "\x1b[0m", "\x1b[38;5;242m", "\x1b[49m", "\x1b]2;title\x07", "\x1b]1;tab\x07",
        "\x1b[?2004h", "\x1b[?2004l", "\x1b[?25l", "\x1b[?25h"
    ]
    chunks = s.split("\n")
    out = []
    for line in chunks:
        if not line.strip():
            out.append(line)
            continue
        if random.random() < 0.25:
            line = noise[random.randrange(len(noise))] + line
        if random.random() < 0.15:
            line = line + noise[random.randrange(len(noise))]
        out.append(line)
    return "\n".join(out)

def nowstamp(offset_min=0):
    """Generate timestamp for script logs"""
    base = datetime.datetime(2025, 9, 6, 0, 3, 10)
    t = base + datetime.timedelta(minutes=offset_min, seconds=random.randint(0, 40))
    return t.strftime("%a %b %d %H:%M:%S %Y")

def mk_prompt(transcript):
    """Create developer and user prompts for the conversation"""
    dev = (
        "You convert terminal transcripts into status reports.\n"
        "Respond with STRICT JSON only, matching the provided schema exactly.\n"
        "Do not include code fences, comments, or extra text."
    )
    user = f"{SCHEMA_TEXT}\nTranscript:\n{transcript}"
    return dev, user

def json_obj(summary, successes, blockers, resources):
    """Create the expected JSON output structure"""
    return [{
        "summary": summary,
        "key_successes": successes,
        "blockers": blockers,
        "resources": resources
    }]

# Scenario builders
def scen_py_tests_ok():
    """Scenario: Python tests pass successfully"""
    ts = nowstamp(0)
    transcript = f"""Script started on {ts}
~/repo │ on main ▓▒░ base Py │ 3.11.8 ─╮
❯ python --version
Python 3.11.8
❯ pytest -q
......................................................
120 passed, 3 skipped in 48.21s
❯ pre-commit run -a
black..............................................Passed
ruff...............................................Passed
mypy...............................................Passed
"""
    transcript = esc(transcript)
    out = json_obj(
        "Ran local test suite and linters successfully on main",
        [{
            "desc": "All tests and linters passed",
            "specifics": "pytest -q; pre-commit (black, ruff, mypy)",
            "adjacent_context": "120 passed, 3 skipped in ~48s on branch main"
        }],
        [],
        ["Merge PR after CI mirrors this result", "Tag the commit if release-ready"]
    )
    return transcript, out

def scen_docker_eof():
    """Scenario: Docker build fails with EOF"""
    ts = nowstamp(5)
    transcript = f"""Script started on {ts}
~/app │ on feature/dockerize ▓▒░ base Py │ 3.12.6 ─╮
❯ docker --version
Docker version 27.0.3, build abcdefg
❯ docker build -t app:latest .
[+] Building  47.5s (12/14)
 => [internal] load .dockerignore                                         0.0s
 => [internal] load build definition from Dockerfile                      0.0s
 => [1/9] FROM python:3.12-slim                                          6.2s
 => [2/9] RUN apt-get update && apt-get install -y build-essential      18.3s
 => [3/9] COPY requirements.txt .                                        0.1s
 => [4/9] RUN pip install -r requirements.txt                           20.6s
 => CANCELED
error: unexpected EOF
"""
    transcript = esc(transcript)
    out = json_obj(
        "Attempted Docker image build; build aborted with unexpected EOF",
        [{
            "desc": "Validated Docker environment version",
            "specifics": "Docker 27.0.3; began multi-stage build",
            "adjacent_context": "Canceled at layer [4/9] pip install"
        }],
        [{
            "desc": "Docker build failed with 'unexpected EOF'",
            "impact": "Image cannot be produced; deploy pipeline blocked",
            "owner_hint": "Infra or DevOps",
            "resolution_hint": "Retry with --no-cache; inspect network, registry creds, or COPY context size"
        }],
        ["Re-run: docker build --no-cache .", "Check Docker daemon logs", "Validate registry login (docker login)"]
    )
    return transcript, out

def scen_git_conflict():
    """Scenario: Git merge conflict"""
    ts = nowstamp(12)
    transcript = f"""Script started on {ts}
~/service │ on feature/refactor-auth ▓▒░
❯ git pull origin main
From github.com:org/service
 * branch            main       -> FETCH_HEAD
Auto-merging auth/handlers.py
CONFLICT (content): Merge conflict in auth/handlers.py
Automatic merge failed; fix conflicts and then commit the result.
❯ git status
On branch feature/refactor-auth
You have unmerged paths.
  (fix conflicts and run "git commit")
"""
    transcript = esc(transcript)
    out = json_obj(
        "Pulled latest main; encountered merge conflict in auth module",
        [{
            "desc": "Fetched latest changes from main",
            "specifics": "git pull origin main",
            "adjacent_context": "Conflict in auth/handlers.py"
        }],
        [{
            "desc": "Merge conflict blocks integration",
            "impact": "Feature branch cannot be merged until resolved",
            "owner_hint": "Author of feature branch",
            "resolution_hint": "Manual resolve in auth/handlers.py; run tests; commit merge"
        }],
        ["Open file diff tool", "Coordinate with auth codeowner for intended logic"]
    )
    return transcript, out

def scen_node_audit():
    """Scenario: Node.js build with security vulnerabilities"""
    ts = nowstamp(20)
    transcript = f"""Script started on {ts}
~/web │ on main ▓▒░ node v20.11 ─╮
❯ node -v
v20.11.1
❯ npm ci
added 178, removed 12, audited 190 packages in 4s
3 vulnerabilities (1 moderate, 2 high)
❯ npm run build
vite v5.1.0 building for production...
✓ 402 modules transformed.
dist/assets/index.abc123.js   210.45 kB
build completed in 12.21s.
"""
    transcript = esc(transcript)
    out = json_obj(
        "Installed front-end deps; build succeeded; audit reports 3 vulnerabilities",
        [{
            "desc": "Front-end assets built successfully",
            "specifics": "npm ci; npm run build (Vite)",
            "adjacent_context": "402 modules transformed; bundle ~210 kB"
        }],
        [{
            "desc": "Security vulnerabilities reported by npm audit",
            "impact": "Potential security risk if deployed without patching",
            "owner_hint": "Front-end team",
            "resolution_hint": "Run `npm audit fix` or upgrade affected deps; consider pinned versions"
        }],
        ["Run: npm audit --production", "Schedule dependency upgrades next sprint"]
    )
    return transcript, out

def scen_db_migration_fail():
    """Scenario: Database migration failure"""
    ts = nowstamp(28)
    transcript = f"""Script started on {ts}
~/api │ on main ▓▒░ ─╮
❯ poetry run alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
ERROR [alembic.util.messaging] Can't locate revision identified by '3f2c0a1e9c5'
  FAILED: Can't locate revision '3f2c0a1e9c5'
"""
    transcript = esc(transcript)
    out = json_obj(
        "Attempted DB migration; missing revision error halted upgrade",
        [{
            "desc": "Verified alembic tooling on project",
            "specifics": "alembic upgrade head invoked under poetry",
            "adjacent_context": "Target revision '3f2c0a1e9c5' not found"
        }],
        [{
            "desc": "Alembic revision missing",
            "impact": "Cannot migrate DB; API deploy blocked",
            "owner_hint": "Backend team / DB owners",
            "resolution_hint": "Ensure migration file exists and is pushed; rebase and re-run"
        }],
        ["git fetch --all; check versions/ migration folder", "Coordinate migration order with teammates"]
    )
    return transcript, out

def scen_k8s_apply_perm():
    """Scenario: Kubernetes RBAC permission denied"""
    ts = nowstamp(35)
    transcript = f"""Script started on {ts}
~/ops │ on main ▓▒░ ─╮
❯ kubectl apply -f deploy.yaml -n staging
Error from server (Forbidden): error when retrieving current configuration:
User "ci-bot" cannot get resource "deployments" in API group "apps" in the namespace "staging"
"""
    transcript = esc(transcript)
    out = json_obj(
        "Kubernetes apply failed due to RBAC permissions on staging",
        [{
            "desc": "Attempted to apply deployment manifest",
            "specifics": "kubectl apply -f deploy.yaml -n staging",
            "adjacent_context": "Service account ci-bot lacks get perms on deployments"
        }],
        [{
            "desc": "RBAC forbids deployment retrieval",
            "impact": "Cannot update staging; release halted",
            "owner_hint": "Platform / SRE",
            "resolution_hint": "Grant role with get/list/update on deployments in staging"
        }],
        ["Open RBAC ticket with exact error", "Temporarily run apply using an admin SA (if policy allows)"]
    )
    return transcript, out

def scen_port_in_use():
    """Scenario: Port already in use"""
    ts = nowstamp(42)
    transcript = f"""Script started on {ts}
~/svc │ on main ▓▒░ ─╮
❯ uvicorn app.main:app --reload --port 8000
INFO:     Will watch for changes in these directories: ['/Users/dev/svc']
ERROR:    [Errno 48] Address already in use
"""
    transcript = esc(transcript)
    out = json_obj(
        "Tried to start dev server; port 8000 already in use",
        [{
            "desc": "Detected running instance on port 8000",
            "specifics": "uvicorn app.main:app --reload --port 8000",
            "adjacent_context": "macOS errno 48"
        }],
        [{
            "desc": "Port conflict",
            "impact": "Local testing blocked",
            "owner_hint": "Developer local env",
            "resolution_hint": "Kill process using port, or start on alternative port"
        }],
        ["Run: lsof -i :8000 | awk 'NR>1{print $2}' | xargs kill -9", "Use --port 8001 temporarily"]
    )
    return transcript, out

def scen_py_version_mismatch():
    """Scenario: Python version incompatibility"""
    ts = nowstamp(50)
    transcript = f"""Script started on {ts}
~/tooling │ on main ▓▒░ ─╮
❯ pyenv local 3.12.6
❯ python --version
Python 3.12.6
❯ pip install -e .
ERROR: This package requires Python >=3.10,<3.12, but the running Python is 3.12.6
"""
    transcript = esc(transcript)
    out = json_obj(
        "Attempted editable install; package rejects Python 3.12",
        [{
            "desc": "Verified interpreter version via pyenv",
            "specifics": "pyenv local 3.12.6; python --version",
            "adjacent_context": "Package requires <3.12"
        }],
        [{
            "desc": "Interpreter version unsupported by package",
            "impact": "Local dev install fails",
            "owner_hint": "Maintainer of package constraints",
            "resolution_hint": "Switch to 3.11.x or relax classifiers and test"
        }],
        ["pyenv shell 3.11.9 && pip install -e .", "Run test matrix for 3.12 support"]
    )
    return transcript, out

def scen_ci_green():
    """Scenario: CI passes and release tag created"""
    ts = nowstamp(58)
    transcript = f"""Script started on {ts}
~/repo │ on main ▓▒░ ─╮
❯ gh run watch --exit-status
✓ Build
✓ Test
✓ Lint
All checks passed
❯ git tag v1.4.0 && git push origin v1.4.0
"""
    transcript = esc(transcript)
    out = json_obj(
        "CI pipeline green; created and pushed v1.4.0 tag",
        [{
            "desc": "All CI checks passing",
            "specifics": "gh run watch --exit-status",
            "adjacent_context": "Build/Test/Lint ✓ on main"
        }, {
            "desc": "Release tag created",
            "specifics": "git tag v1.4.0 && git push origin v1.4.0",
            "adjacent_context": "Version v1.4.0"
        }],
        [],
        ["Publish release notes", "Promote to staging"]
    )
    return transcript, out

def scen_ollama_version_check():
    """Scenario: Checking Ollama and Python versions"""
    ts = nowstamp(65)
    transcript = f"""Script started on {ts}
~/Documents/GitHub/InnerBoard-local │ on main !10 ?7 ▓▒░ base Py │ 3.12.6 ─╮
❯ python --version
Python 3.12.6
❯ ollama --version
ollama version is 0.11.8
❯ python -v
import _frozen_importlib # frozen
import _imp # builtin
# ... many import lines ...
Python 3.12.6 (main, Nov 22 2024, 20:50:01) [Clang 15.0.0 (clang-1500.3.9.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> exit()
"""
    transcript = esc(transcript)
    out = json_obj(
        "Verified Python 3.12.6 and Ollama 0.11.8 environment versions",
        [{
            "desc": "Confirmed Python interpreter version",
            "specifics": "python --version; python -v interactive session",
            "adjacent_context": "Python 3.12.6 on Darwin with Clang 15.0.0"
        }, {
            "desc": "Verified Ollama installation",
            "specifics": "ollama --version",
            "adjacent_context": "Version 0.11.8 installed"
        }],
        [],
        ["Document runtime requirements in README", "Consider pinning versions in pyproject.toml"]
    )
    return transcript, out

def scen_terraform_plan():
    """Scenario: Terraform infrastructure planning"""
    ts = nowstamp(70)
    transcript = f"""Script started on {ts}
~/infra │ on feature/add-monitoring ▓▒░ ─╮
❯ terraform --version
Terraform v1.5.7
❯ terraform plan
Terraform will perform the following actions:

  # aws_cloudwatch_log_group.app_logs will be created
  + resource "aws_cloudwatch_log_group" "app_logs" {{
      + arn               = (known after apply)
      + id                = (known after apply)
      + name              = "/aws/lambda/my-app"
      + retention_in_days = 14
    }}

Plan: 1 to add, 0 to change, 0 to destroy.
"""
    transcript = esc(transcript)
    out = json_obj(
        "Planned Terraform infrastructure changes for monitoring setup",
        [{
            "desc": "Terraform plan executed successfully",
            "specifics": "terraform plan on feature/add-monitoring branch",
            "adjacent_context": "1 resource to add (CloudWatch log group), 14-day retention"
        }],
        [],
        ["Review plan with team before apply", "Consider longer retention for production logs"]
    )
    return transcript, out

def scen_redis_connection_fail():
    """Scenario: Redis connection failure during development"""
    ts = nowstamp(75)
    transcript = f"""Script started on {ts}
~/api │ on main ▓▒░ ─╮
❯ redis-cli ping
Could not connect to Redis at 127.0.0.1:6379: Connection refused
❯ brew services list | grep redis
redis                    stopped
❯ brew services start redis
==> Successfully started `redis` (label: homebrew.mxcl.redis)
❯ redis-cli ping
PONG
"""
    transcript = esc(transcript)
    out = json_obj(
        "Redis service was down; restarted successfully",
        [{
            "desc": "Redis service restarted via Homebrew",
            "specifics": "brew services start redis; redis-cli ping returned PONG",
            "adjacent_context": "Local Redis on port 6379"
        }],
        [{
            "desc": "Redis connection initially failed",
            "impact": "Local development blocked until service restart",
            "owner_hint": "Developer environment",
            "resolution_hint": "Check Redis service status and restart if needed"
        }],
        ["Add Redis health check to dev setup script", "Document Redis as development dependency"]
    )
    return transcript, out

def scen_webpack_build_slow():
    """Scenario: Webpack build performance issues"""
    ts = nowstamp(80)
    transcript = f"""Script started on {ts}
~/frontend │ on main ▓▒░ node v18.17 ─╮
❯ npm run build
> frontend@1.0.0 build
> webpack --mode production

asset main.js 2.1 MiB [emitted] [minimized] (name: main)
asset main.css 45.2 KiB [emitted] [minimized] (name: main)
webpack 5.88.2 compiled successfully in 47382 ms
❯ npm run build:analyze
Bundle size: 2.1MB (too large!)
Largest chunks: lodash (400KB), moment (350KB), unused deps (300KB)
"""
    transcript = esc(transcript)
    out = json_obj(
        "Webpack build successful but bundle size too large at 2.1MB",
        [{
            "desc": "Production build completed successfully",
            "specifics": "webpack --mode production in 47.3s",
            "adjacent_context": "Main bundle 2.1MB, CSS 45.2KB"
        }],
        [{
            "desc": "Bundle size exceeds performance budget",
            "impact": "Slow page load times affecting user experience",
            "owner_hint": "Frontend team",
            "resolution_hint": "Remove unused dependencies, implement code splitting, tree shaking"
        }],
        ["Replace moment.js with date-fns", "Implement dynamic imports for large libraries", "Run bundle analyzer regularly"]
    )
    return transcript, out

def scen_mysql_migration():
    """Scenario: Database migration execution"""
    ts = nowstamp(85)
    transcript = f"""Script started on {ts}
~/backend │ on main ▓▒░ ─╮
❯ php artisan migrate:status
+------+------------------------------------------------+-------+
| Ran? | Migration                                      | Batch |
+------+------------------------------------------------+-------+
| Yes  | 2023_01_01_000000_create_users_table          | 1     |
| Yes  | 2023_01_15_000000_create_posts_table          | 1     |
| No   | 2023_02_01_000000_add_published_at_to_posts   | 2     |
+------+------------------------------------------------+-------+
❯ php artisan migrate
Migrating: 2023_02_01_000000_add_published_at_to_posts
Migrated:  2023_02_01_000000_add_published_at_to_posts (45.23ms)
"""
    transcript = esc(transcript)
    out = json_obj(
        "Database migration executed successfully for posts table",
        [{
            "desc": "Migration applied successfully",
            "specifics": "php artisan migrate; added published_at column to posts",
            "adjacent_context": "Migration completed in 45.23ms, batch 2"
        }],
        [],
        ["Test new column functionality", "Update model and API documentation"]
    )
    return transcript, out

def scen_ssl_cert_renewal():
    """Scenario: SSL certificate renewal process"""
    ts = nowstamp(90)
    transcript = f"""Script started on {ts}
~/ops │ on main ▓▒░ ─╮
❯ certbot certificates
Found the following certs:
  Certificate Name: api.example.com
    Serial Number: 4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b
    Key Type: RSA
    Domains: api.example.com
    Expiry Date: 2025-09-15 12:00:00+00:00 (VALID: 7 days)
❯ certbot renew --dry-run
Saving debug log to /var/log/letsencrypt/letsencrypt.log
Processing /etc/letsencrypt/renewal/api.example.com.conf
Cert not yet due for renewal
The following certificates are not due for renewal yet:
  /etc/letsencrypt/live/api.example.com/fullchain.pem expires on 2025-09-15 (skipped)
❯ certbot renew
Cert not yet due for renewal
"""
    transcript = esc(transcript)
    out = json_obj(
        "SSL certificate checked; renewal not yet needed (7 days remaining)",
        [{
            "desc": "Certificate status verified",
            "specifics": "certbot certificates; certbot renew --dry-run",
            "adjacent_context": "api.example.com expires 2025-09-15, 7 days remaining"
        }],
        [],
        ["Set up automated renewal monitoring", "Schedule renewal check in 5 days"]
    )
    return transcript, out

def scen_elasticsearch_indexing():
    """Scenario: Elasticsearch index management"""
    ts = nowstamp(95)
    transcript = f"""Script started on {ts}
~/search │ on main ▓▒░ ─╮
❯ curl -X GET "localhost:9200/_cat/indices?v"
health status index    uuid                   pri rep docs.count docs.deleted store.size pri.store.size
yellow open   products 5Gm4qF2kRoWaQN2m8vE7Kw   1   1      15420            0     12.4mb         12.4mb
❯ curl -X POST "localhost:9200/products/_refresh"
{{"_shards":{{"total":2,"successful":1,"failed":0}}}}
❯ curl -X GET "localhost:9200/products/_search?size=0"
{{"took":5,"timed_out":false,"_shards":{{"total":1,"successful":1,"skipped":0,"failed":0}},"hits":{{"total":{{"value":15420,"relation":"eq"}}}}}}
"""
    transcript = esc(transcript)
    out = json_obj(
        "Elasticsearch products index refreshed; 15,420 documents indexed",
        [{
            "desc": "Index status verified and refreshed",
            "specifics": "curl _cat/indices; _refresh; _search with size=0",
            "adjacent_context": "Products index: 15,420 docs, 12.4MB, yellow health"
        }],
        [{
            "desc": "Index health status is yellow",
            "impact": "Potential performance degradation or availability risk",
            "owner_hint": "Search team / DevOps",
            "resolution_hint": "Check replica configuration and cluster node status"
        }],
        ["Investigate yellow health status", "Consider adding replica nodes", "Monitor index performance"]
    )
    return transcript, out

def scen_ansible_deployment():
    """Scenario: Ansible playbook deployment"""
    ts = nowstamp(100)
    transcript = f"""Script started on {ts}
~/ansible │ on main ▓▒░ ─╮
❯ ansible-playbook -i inventory/production deploy.yml --check
PLAY [Deploy application] ****************************************************

TASK [Update application code] ***********************************************
changed: [web-01]
changed: [web-02]

TASK [Restart application service] *******************************************
changed: [web-01]
changed: [web-02]

PLAY RECAP ********************************************************************
web-01                     : ok=2    changed=2    unreachable=0    failed=0
web-02                     : ok=2    changed=2    unreachable=0    failed=0
"""
    transcript = esc(transcript)
    out = json_obj(
        "Ansible deployment dry-run successful on production inventory",
        [{
            "desc": "Deployment playbook validated successfully",
            "specifics": "ansible-playbook --check on production inventory",
            "adjacent_context": "2 tasks changed on web-01 and web-02, no failures"
        }],
        [],
        ["Execute actual deployment: ansible-playbook deploy.yml", "Monitor application health post-deployment"]
    )
    return transcript, out

def scen_monitoring_alert():
    """Scenario: Investigating monitoring alerts"""
    ts = nowstamp(105)
    transcript = f"""Script started on {ts}
~/monitoring │ on main ▓▒░ ─╮
❯ kubectl get pods -n monitoring
NAME                          READY   STATUS    RESTARTS   AGE
prometheus-0                  1/1     Running   0          2d
grafana-7b8c9d4f5-x2n8m      1/1     Running   0          2d
alertmanager-0                1/1     Running   0          2d
❯ kubectl logs prometheus-0 -n monitoring --tail=50
level=warn ts=2025-09-06T05:30:15.123Z caller=scrape.go:1234 component=scrape_manager target=http://api-service:8080/metrics msg="scrape failed" err="context deadline exceeded"
level=warn ts=2025-09-06T05:30:45.456Z caller=scrape.go:1234 component=scrape_manager target=http://api-service:8080/metrics msg="scrape failed" err="context deadline exceeded"
❯ kubectl get svc api-service -n default
NAME          TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
api-service   ClusterIP   10.96.123.45    <none>        8080/TCP   5d
"""
    transcript = esc(transcript)
    out = json_obj(
        "Prometheus scrape failures identified for api-service metrics endpoint",
        [{
            "desc": "Monitoring stack health verified",
            "specifics": "kubectl get pods -n monitoring; all pods running",
            "adjacent_context": "Prometheus, Grafana, AlertManager running for 2 days"
        }],
        [{
            "desc": "Prometheus scrape timeouts on api-service",
            "impact": "Missing metrics data affecting monitoring and alerting",
            "owner_hint": "API team / SRE",
            "resolution_hint": "Check api-service health and metrics endpoint performance"
        }],
        ["Investigate api-service /metrics endpoint latency", "Increase scrape timeout if needed", "Check service discovery configuration"]
    )
    return transcript, out

def scen_load_testing():
    """Scenario: Load testing with Apache Bench"""
    ts = nowstamp(110)
    transcript = f"""Script started on {ts}
~/testing │ on main ▓▒░ ─╮
❯ ab -n 1000 -c 10 http://localhost:8000/api/health
This is ApacheBench, Version 2.3
Server Software:        nginx/1.21.0
Server Hostname:        localhost
Server Port:            8000

Document Path:          /api/health
Document Length:        15 bytes

Concurrency Level:      10
Time taken for tests:   2.456 seconds
Complete requests:      1000
Failed requests:        0
Total transferred:      235000 bytes
Requests per second:    407.14 [#/sec] (mean)
Time per request:       24.563 [ms] (mean)
Time per request:       2.456 [ms] (mean, across all concurrent requests)
"""
    transcript = esc(transcript)
    out = json_obj(
        "Load test completed: 407 req/sec with 24ms avg response time",
        [{
            "desc": "Load test executed successfully",
            "specifics": "ab -n 1000 -c 10 on /api/health endpoint",
            "adjacent_context": "1000 requests, 0 failures, 407 req/sec, 24ms avg latency"
        }],
        [],
        ["Baseline established for health endpoint performance", "Run tests against other critical endpoints", "Set up automated performance monitoring"]
    )
    return transcript, out

def scen_backup_verification():
    """Scenario: Database backup verification"""
    ts = nowstamp(115)
    transcript = f"""Script started on {ts}
~/backups │ on main ▓▒░ ─╮
❯ ls -la /backups/postgres/
total 2.1G
-rw-r--r-- 1 postgres postgres 523M Sep  5 23:00 db_backup_2025-09-05.sql.gz
-rw-r--r-- 1 postgres postgres 521M Sep  4 23:00 db_backup_2025-09-04.sql.gz
-rw-r--r-- 1 postgres postgres 519M Sep  3 23:00 db_backup_2025-09-03.sql.gz
❯ gunzip -t /backups/postgres/db_backup_2025-09-05.sql.gz
❯ echo $?
0
❯ zcat /backups/postgres/db_backup_2025-09-05.sql.gz | head -20
-- PostgreSQL database dump
-- Dumped from database version 13.8
-- Started on 2025-09-05 23:00:01 UTC
SET statement_timeout = 0;
CREATE TABLE public.users (id SERIAL PRIMARY KEY...
"""
    transcript = esc(transcript)
    out = json_obj(
        "Database backup verification successful; latest backup is valid",
        [{
            "desc": "Backup integrity verified",
            "specifics": "gunzip -t on latest backup; file structure validated",
            "adjacent_context": "523MB backup from Sep 5, PostgreSQL 13.8"
        }],
        [],
        ["Backup rotation working correctly", "Consider testing restore process monthly", "Monitor backup size growth"]
    )
    return transcript, out

def scen_go_build_error():
    """Scenario: Go build compilation error"""
    ts = nowstamp(120)
    transcript = f"""Script started on {ts}
~/go-service │ on feature/refactor ▓▒░ ─╮
❯ go version
go version go1.21.3 darwin/amd64
❯ go build ./cmd/server
# github.com/company/go-service/internal/auth
internal/auth/jwt.go:45:15: undefined: jwt.ParseWithClaims
internal/auth/jwt.go:52:9: user.ID undefined (type User has no field or method ID)
❯ go mod tidy
go: finding module for package github.com/golang-jwt/jwt/v5
go: added github.com/golang-jwt/jwt/v5 v5.0.0
❯ go build ./cmd/server
Build successful: server
"""
    transcript = esc(transcript)
    out = json_obj(
        "Go build failed due to missing imports; resolved with go mod tidy",
        [{
            "desc": "Go module dependencies updated",
            "specifics": "go mod tidy; added golang-jwt/jwt/v5 v5.0.0",
            "adjacent_context": "Build successful after dependency resolution"
        }],
        [{
            "desc": "Undefined symbols in auth package",
            "impact": "Build failure preventing service deployment",
            "owner_hint": "Go service team",
            "resolution_hint": "Update import paths and struct field names"
        }],
        ["Update JWT import to v5 API", "Fix User struct field references", "Run go mod tidy after dependency changes"]
    )
    return transcript, out

def scen_nginx_config_test():
    """Scenario: Nginx configuration testing"""
    ts = nowstamp(125)
    transcript = f"""Script started on {ts}
~/nginx │ on main ▓▒░ ─╮
❯ nginx -v
nginx version: nginx/1.21.6
❯ nginx -t
nginx: [emerg] invalid number of arguments in "proxy_pass" directive in /etc/nginx/sites-enabled/api.conf:15
nginx: configuration file /etc/nginx/nginx.conf test failed
❯ vim /etc/nginx/sites-enabled/api.conf
# Fixed proxy_pass directive
❯ nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
❯ sudo nginx -s reload
"""
    transcript = esc(transcript)
    out = json_obj(
        "Nginx configuration error fixed; config test passed and reloaded",
        [{
            "desc": "Nginx configuration validated and reloaded",
            "specifics": "nginx -t; sudo nginx -s reload",
            "adjacent_context": "Fixed proxy_pass directive in api.conf line 15"
        }],
        [{
            "desc": "Invalid proxy_pass directive syntax",
            "impact": "Nginx config test failed preventing reload",
            "owner_hint": "DevOps / Infrastructure team",
            "resolution_hint": "Fix proxy_pass syntax and test before reload"
        }],
        ["Test nginx config before applying changes", "Use nginx -t in CI/CD pipeline", "Document nginx configuration patterns"]
    )
    return transcript, out

def scen_aws_cli_deployment():
    """Scenario: AWS CLI deployment operations"""
    ts = nowstamp(130)
    transcript = f"""Script started on {ts}
~/aws │ on main ▓▒░ ─╮
❯ aws --version
aws-cli/2.13.25 Python/3.11.5 Darwin/22.6.0 exe/x86_64
❯ aws sts get-caller-identity
{{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/deploy-user"
}}
❯ aws s3 sync ./dist s3://my-app-frontend/ --delete
upload: dist/index.html to s3://my-app-frontend/index.html
upload: dist/assets/app.js to s3://my-app-frontend/assets/app.js
upload: dist/assets/app.css to s3://my-app-frontend/assets/app.css
delete: s3://my-app-frontend/old-file.js
❯ aws cloudfront create-invalidation --distribution-id E1234567890123 --paths "/*"
{{
    "Invalidation": {{
        "Id": "I2J3K4L5M6N7O8P9Q0R1S2T3U4V5W6X7Y8Z9",
        "Status": "InProgress"
    }}
}}
"""
    transcript = esc(transcript)
    out = json_obj(
        "AWS S3 deployment successful with CloudFront cache invalidation",
        [{
            "desc": "Frontend assets deployed to S3",
            "specifics": "aws s3 sync ./dist with --delete flag",
            "adjacent_context": "Uploaded 3 files, deleted 1 old file"
        }, {
            "desc": "CloudFront cache invalidation initiated",
            "specifics": "aws cloudfront create-invalidation for all paths",
            "adjacent_context": "Distribution E1234567890123, invalidation in progress"
        }],
        [],
        ["Monitor invalidation completion", "Set up automated deployment pipeline", "Consider using CloudFront Functions for cache control"]
    )
    return transcript, out

def scen_java_maven_test():
    """Scenario: Maven test execution with failures"""
    ts = nowstamp(135)
    transcript = f"""Script started on {ts}
~/java-api │ on main ▓▒░ ─╮
❯ java -version
openjdk version "17.0.7" 2023-04-18
❯ mvn --version
Apache Maven 3.9.4
❯ mvn test
[INFO] Scanning for projects...
[INFO] Running com.example.api.UserServiceTest
[ERROR] Tests run: 5, Failures: 2, Errors: 0, Skipped: 0
[ERROR] Failures: 
[ERROR]   UserServiceTest.testCreateUser:42 expected:<201> but was:<400>
[ERROR]   UserServiceTest.testDeleteUser:58 NullPointerException
[INFO] Results:
[ERROR] Tests run: 5, Failures: 2, Errors: 0, Skipped: 0, Time elapsed: 2.456 s
[INFO] BUILD FAILURE
"""
    transcript = esc(transcript)
    out = json_obj(
        "Maven test execution failed; 2 test failures in UserServiceTest",
        [{
            "desc": "Maven test suite executed",
            "specifics": "mvn test; 5 tests run in 2.456s",
            "adjacent_context": "Java 17, Maven 3.9.4"
        }],
        [{
            "desc": "Test failures in UserServiceTest",
            "impact": "Build pipeline blocked; potential regression in user service",
            "owner_hint": "Java API team",
            "resolution_hint": "Fix testCreateUser status code and testDeleteUser null handling"
        }],
        ["Debug testCreateUser expected vs actual status codes", "Fix NullPointerException in testDeleteUser", "Review recent changes to UserService"]
    )
    return transcript, out

def scen_prometheus_query():
    """Scenario: Prometheus metrics querying"""
    ts = nowstamp(140)
    transcript = f"""Script started on {ts}
~/monitoring │ on main ▓▒░ ─╮
❯ curl -s "http://localhost:9090/api/v1/query?query=up" | jq '.data.result[] | select(.metric.job=="api-service")'
{{
  "metric": {{
    "__name__": "up",
    "instance": "api-service:8080",
    "job": "api-service"
  }},
  "value": [
    1694025600,
    "0"
  ]
}}
❯ curl -s "http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])" | jq '.data.result[0].value[1]'
"127.45"
❯ curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))" | jq '.data.result[0].value[1]'
"0.234"
"""
    transcript = esc(transcript)
    out = json_obj(
        "Prometheus metrics analysis shows api-service down, 127 req/s, 234ms p95 latency",
        [{
            "desc": "Prometheus metrics queried successfully",
            "specifics": "up, rate(http_requests_total), histogram_quantile queries",
            "adjacent_context": "127.45 req/s rate, 234ms p95 latency"
        }],
        [{
            "desc": "API service health check failing",
            "impact": "Service appears down (up=0) affecting availability monitoring",
            "owner_hint": "API team / SRE",
            "resolution_hint": "Investigate api-service:8080 health and connectivity"
        }],
        ["Check api-service pod/container status", "Verify health check endpoint", "Review service discovery configuration"]
    )
    return transcript, out

SCENARIOS = [
    scen_py_tests_ok,
    scen_docker_eof,
    scen_git_conflict,
    scen_node_audit,
    scen_db_migration_fail,
    scen_k8s_apply_perm,
    scen_port_in_use,
    scen_py_version_mismatch,
    scen_ci_green,
    scen_ollama_version_check,
    scen_terraform_plan,
    scen_redis_connection_fail,
    scen_webpack_build_slow,
    scen_mysql_migration,
    scen_ssl_cert_renewal,
    scen_elasticsearch_indexing,
    scen_ansible_deployment,
    scen_monitoring_alert,
    scen_load_testing,
    scen_backup_verification,
    scen_go_build_error,
    scen_nginx_config_test,
    scen_aws_cli_deployment,
    scen_java_maven_test,
    scen_prometheus_query,
]

def make_messages(transcript, out_json):
    """Create message format compatible with GPT-OSS Harmony format"""
    return [
        {
            "role": "developer", 
            "content": (
                "# Instructions\n\n"
                "reasoning language: English\n\n"
                "You convert terminal transcripts into structured session reports.\n"
                "Respond with STRICT JSON only, matching the provided schema exactly.\n"
                "Do not include code fences, comments, or extra text.\n\n"
                f"{SCHEMA_TEXT}"
            )
        },
        {
            "role": "user", 
            "content": f"Terminal transcript:\n{transcript}"
        },
        {
            "role": "assistant",
            "content": json.dumps(out_json, ensure_ascii=False)
        }
    ]

def synthesize(n=48):
    """Generate synthetic training data"""
    rows_pairs = []
    rows_msgs = []
    
    for i in range(n):
        scen = random.choice(SCENARIOS)
        transcript, out_json = scen()
        
        # Introduce minor noisy keystrokes sometimes
        if random.random() < 0.3:
            transcript += "\n❯ gti status\nbash: gti: command not found\n"
        
        item_pair = {
            "input": transcript,
            "output": out_json
        }
        rows_pairs.append(item_pair)
        
        # Create GPT-OSS Harmony format messages
        harmony_messages = make_messages(transcript, out_json)
        rows_msgs.append({"messages": harmony_messages})
    
    return rows_pairs, rows_msgs

def main():
    """Generate and save synthetic training data"""
    pairs, msgs = synthesize(128)  # Increased from 64 to 128 examples
    
    # Create data directory
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    pairs_path = data_dir / "pairs.jsonl"
    msgs_path = data_dir / "harmony_messages.jsonl"
    
    with open(pairs_path, "w") as f:
        for row in pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    with open(msgs_path, "w") as f:
        for row in msgs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    print(f"Generated {len(pairs)} training examples")
    print(f"Saved to: {pairs_path} and {msgs_path}")
    print(f"The harmony_messages.jsonl file is compatible with GPT-OSS Colab notebook")
    
    # Show a tiny preview (first example)
    print("\nPreview of Harmony format message:")
    print("Messages structure:")
    for i, msg in enumerate(msgs[0]["messages"]):
        print(f"  {i+1}. Role: {msg['role']}")
        content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
        print(f"     Content: {content_preview}")
        print()
    
    print("JSON Output Preview:")
    print(json.dumps(pairs[0]["output"], indent=2)[:300] + "...")

if __name__ == "__main__":
    main()
