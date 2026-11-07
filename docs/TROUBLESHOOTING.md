# Troubleshooting & Failure Scenarios
Always check: `curl http://<ip>/api/health?deep=1` and Storage info page. On a VM: `az vmss run-command invoke -g $RG -n backend-vmss --instance-id 0 --command-id RunShellScript --scripts "journalctl -u ecommerce -n 50 --no-pager; cloud-init status"`.

| # | Scenario | Trigger | Symptom (API) | Explain | Fix |
|---|---|---|---|---|---|
| 1 | Managed Identity disabled | `./configure-vmss.sh mi-disable` | 503 `AUTHENTICATION_FAILED`; dashboard "token ✖" | IMDS has no identity → no Entra token | `mi-enable`, then `configure-rbac.sh add` (new principal ID!) |
| 2 | RBAC removed | `./configure-rbac.sh remove` (wait 1-5 min) | 403 `AUTHORIZATION_FAILED` | Authenticated but not authorised | `configure-rbac.sh add` |
| 3 | NSG blocks traffic | `./test-storage.sh nsg-block` | Browser: 502/504 on `/api/*`, static pages still load | Priority 90 deny beats 100 allow | `nsg-unblock` |
| 4 | Private DNS broken | `./test-storage.sh dns-break` | 403/503 from storage; `nslookup <acct>.blob.core.windows.net` on VM returns public IP | No VNet link → public IP → blocked | `dns-fix` |
| 5 | Public access disabled | `./test-storage.sh public-access` | Public curl: 403 `AuthorizationFailure`; backend deep health OK | Only the private endpoint path works | — |
| 6 | Autoscaling | `./configure-vmss.sh load` | Instance count 2→3→4 in 5-10 min; `stop-load` → scale in | CPU rule + cooldown | — |

Other issues: site not up after deploy → cloud-init still running (wait 5 min); `pip` fails → NAT gateway/outbound; `RoleAssignmentExists`/`AuthorizationFailed` on deploy → you need Owner or User Access Administrator; StorageAccountAlreadyTaken → `STORAGE_NAME=<unique> ./deploy.sh`; 409 CONFLICT in UI → someone changed the blob, reload (ETag protection working); SSH → create `AzureBastionSubnet` 10.20.250.0/26 + Bastion (NSG rule already allows it) or use `az vmss run-command`.

## Phase 2 additions
| Symptom | Cause | Fix |
|---|---|---|
| 401 on every call | token expired (8 h) or `SESSION_SECRET` differs between instances | log in again; redeploy/update-app so all instances share the same env file |
| Login works on one refresh, fails next | instances have different `SESSION_SECRET` | `./update-app.sh backend` |
| Order response shows `queue_status: Retrying` | Queue/Table unreachable or role missing | fix cause (`configure-rbac.sh add`, DNS link), then Admin -> **Reconcile** |
| 403 AUTHORIZATION_FAILED only on orders/queue | Queue/Table role missing or PE DNS zone not linked | `ROLE="Storage Queue Data Contributor" ./configure-rbac.sh add`; check `privatelink.queue/table` zones |
| Message keeps reappearing | consumer failing; visibility timeout 30 s | read Admin consumer output / `journalctl -u ecommerce`; after 3 attempts it moves to the poison queue |
| Seller cannot publish | needs price > 0, stock >= 1, image | complete the form |
| No demo users | blank seed passwords | `./update-app.sh backend` (seeds on start) |
