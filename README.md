# multi-client-ruleset

个人使用的多客户端分流规则同步器。只维护两份源文件：

- `source/direct.json`：需要直连的域名或 IP 段
- `source/proxy.json`：需要代理的域名或 IP 段

提交修改后，GitHub Actions 会自动校验、去重并生成各客户端的规则集，同时把 sing-box JSON 编译成二进制 `.srs`。

## 支持情况

| 客户端 | 远程规则集 | 生成目录 | 说明 |
| --- | --- | --- | --- |
| Clash | ✅ | `generated/clash` | classical YAML rule-provider |
| Mihomo | ✅ | `generated/mihomo` | classical YAML rule-provider |
| sing-box | ✅ | `generated/sing-box` | source JSON 与 binary SRS |
| Shadowrocket | ✅ | `generated/shadowrocket` | `RULE-SET` 文本规则 |
| Quantumult X | ✅ | `generated/quantumult-x` | `filter_remote` 规则，策略可强制覆盖 |
| Loon | ✅ | `generated/loon` | `[Remote Rule]` 远程规则 |
| Surge | ✅ | `generated/surge` | `RULE-SET` 文本规则 |
| Surfboard | ✅ | `generated/surfboard` | Surge 风格 `RULE-SET` |
| Hiddify | ⚠️ 间接支持 | 使用 `generated/sing-box` | 需要能导入含 rule-set 引用的完整 sing-box 配置；App UI 不保证能单独添加规则集 |

## 添加规则

在对应源文件的 `rules` 数组中追加一项：

```json
{ "type": "domain-suffix", "value": "example.com" }
```

支持三种类型：

```json
{ "type": "domain", "value": "api.example.com" }
{ "type": "domain-suffix", "value": "example.com" }
{ "type": "ip-cidr", "value": "203.0.113.0/24" }
```

`domain` 只匹配完整域名；`domain-suffix` 同时匹配根域名及其所有子域名。相同规则不能同时出现在 direct 与 proxy 中，否则构建会失败。

本地生成：

```bash
python3 scripts/generate.py
```

以下示例中的 `<USER>` 为 `pairli`，仓库为 `multi-client-ruleset`。

## Clash / Mihomo

在配置中加入两个 provider，然后把引用放在通用规则之前：

```yaml
rule-providers:
  custom-direct:
    type: http
    behavior: classical
    format: yaml
    url: https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/mihomo/direct.yaml
    path: ./ruleset/custom-direct.yaml
    interval: 86400
  custom-proxy:
    type: http
    behavior: classical
    format: yaml
    url: https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/mihomo/proxy.yaml
    path: ./ruleset/custom-proxy.yaml
    interval: 86400

rules:
  - RULE-SET,custom-direct,DIRECT
  - RULE-SET,custom-proxy,节点选择
```

Clash 使用方式相同，把 URL 中的 `mihomo` 改为 `clash` 即可。

## sing-box

在 `route.rule_set` 中声明远程 SRS：

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "custom-direct",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/sing-box/direct.srs"
      },
      {
        "type": "remote",
        "tag": "custom-proxy",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/sing-box/proxy.srs"
      }
    ],
    "rules": [
      { "rule_set": "custom-direct", "action": "route", "outbound": "direct" },
      { "rule_set": "custom-proxy", "action": "route", "outbound": "节点选择" }
    ]
  }
}
```

自定义规则应放在中国域名、GeoIP 和最终兜底规则之前。

## Shadowrocket

在 `[Rule]` 中加入：

```ini
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/shadowrocket/direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/shadowrocket/proxy.list,PROXY
```

把 `PROXY` 换成配置中实际存在的策略组名称。

## Quantumult X

在 `[filter_remote]` 中加入：

```ini
https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/quantumult-x/direct.list, tag=custom-direct, force-policy=direct, enabled=true
https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/quantumult-x/proxy.list, tag=custom-proxy, force-policy=节点选择, enabled=true
```

`force-policy` 会覆盖规则文件内的默认 `direct` / `proxy` 策略。

## Loon

在 `[Remote Rule]` 中加入：

```ini
https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/loon/direct.list, policy=DIRECT, tag=custom-direct, enabled=true
https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/loon/proxy.list, policy=节点选择, tag=custom-proxy, enabled=true
```

## Surge

在 `[Rule]` 中加入：

```ini
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/surge/direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/surge/proxy.list,节点选择
```

## Surfboard

在 `[Rule]` 中加入：

```ini
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/surfboard/direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/pairli/multi-client-ruleset/main/generated/surfboard/proxy.list,节点选择
```

## Hiddify

Hiddify 基于 sing-box，但当前更适合导入完整配置或订阅，而不是独立粘贴一条远程规则集 URL。若所用版本允许导入完整 sing-box 配置，可复用上面的 sing-box SRS 地址；否则需要在订阅模板生成阶段把这两个 rule-set 注入配置。

## 生成目录

`generated/` 是自动产物，不要直接编辑。任何手工改动都会在下一次构建时被覆盖。
