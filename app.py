"""
自建 DDNS 中转服务：路由器发请求过来，本服务用阿里云 AccessKey 签名后
调用阿里云云解析 API，把指定域名的 A 记录更新为路由器的公网 IP。

密钥只配置在这台服务器上（环境变量），不会下发给路由器或第三方。
"""
import os
import logging

from flask import Flask, request, jsonify
from alibabacloud_tea_openapi.models import Config
from alibabacloud_alidns20150109.client import Client
from alibabacloud_alidns20150109 import models as alidns_models

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ddns-proxy")

app = Flask(__name__)

# 本服务自己的访问令牌，防止任何人都能调用你的 DDNS 接口
AUTH_TOKEN = os.environ["DDNS_PROXY_TOKEN"]

ACCESS_KEY_ID = os.environ["ALIYUN_ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = os.environ["ALIYUN_ACCESS_KEY_SECRET"]


def get_client() -> Client:
    config = Config(
        access_key_id=ACCESS_KEY_ID,
        access_key_secret=ACCESS_KEY_SECRET,
        endpoint="alidns.cn-hangzhou.aliyuncs.com",
    )
    return Client(config)


def split_domain(fqdn: str) -> tuple[str, str]:
    """把 proxy.example.com 拆成 (RR=proxy, 主域名=example.com)"""
    parts = fqdn.split(".")
    if len(parts) < 2:
        raise ValueError(f"invalid domain: {fqdn}")
    rr = ".".join(parts[:-2]) or "@"
    main_domain = ".".join(parts[-2:])
    return rr, main_domain


def update_record(fqdn: str, ip: str) -> str:
    rr, main_domain = split_domain(fqdn)
    client = get_client()

    describe_req = alidns_models.DescribeDomainRecordsRequest(
        domain_name=main_domain,
        rrkey_word=rr,
        type="A",
    )
    records = client.describe_domain_records(describe_req).body.domain_records.record

    if records:
        record_id = records[0].record_id
        update_req = alidns_models.UpdateDomainRecordRequest(
            record_id=record_id,
            rr=rr,
            type="A",
            value=ip,
        )
        client.update_domain_record(update_req)
        return f"updated {fqdn} -> {ip}"
    else:
        add_req = alidns_models.AddDomainRecordRequest(
            domain_name=main_domain,
            rr=rr,
            type="A",
            value=ip,
        )
        client.add_domain_record(add_req)
        return f"created {fqdn} -> {ip}"


@app.get("/ddns")
def ddns():
    if request.args.get("token") != AUTH_TOKEN:
        return jsonify(status="error", data="unauthorized"), 401

    domain = request.args.get("domain")
    if not domain:
        return jsonify(status="error", data="missing domain"), 400

    # 优先用请求里传的 ip 参数，没传就用看到的客户端公网 IP
    ip = request.args.get("ip") or request.remote_addr

    try:
        result = update_record(domain, ip)
        log.info(result)
        return jsonify(status="finished", data=result)
    except Exception as exc:  # noqa: BLE001
        log.exception("ddns update failed")
        return jsonify(status="error", data=str(exc)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6180)
