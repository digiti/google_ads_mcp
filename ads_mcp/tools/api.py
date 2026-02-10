# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module contains tools for interacting with the Google Ads API."""

import os
from typing import Any
import json

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.util import get_nested_attr
from google.ads.googleads.v23.services.services.customer_service import CustomerServiceClient
from google.ads.googleads.v23.services.services.google_ads_service import GoogleAdsServiceClient
from google.oauth2.credentials import Credentials
import proto
import yaml

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.utils import ROOT_DIR


_ADS_CLIENT: GoogleAdsClient | None = None


def _get_client_from_env() -> GoogleAdsClient | None:
  """Attempts to build a GoogleAdsClient from environment variables.

  Required env vars:
      GOOGLE_ADS_DEVELOPER_TOKEN
      GOOGLE_ADS_CLIENT_ID
      GOOGLE_ADS_CLIENT_SECRET
      GOOGLE_ADS_REFRESH_TOKEN

  Optional env vars:
      GOOGLE_ADS_LOGIN_CUSTOMER_ID

  Returns:
      A GoogleAdsClient if all required env vars are set, else None.
  """
  developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
  client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
  client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
  refresh_token = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")

  if not all([developer_token, client_id, client_secret, refresh_token]):
    return None

  config = {
      "developer_token": developer_token,
      "client_id": client_id,
      "client_secret": client_secret,
      "refresh_token": refresh_token,
      "use_proto_plus": True,
  }

  login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
  login_customer_id = login_customer_id.replace("-", "").strip()
  if login_customer_id:
    config["login_customer_id"] = login_customer_id

  return GoogleAdsClient.load_from_dict(config)


def get_ads_client() -> GoogleAdsClient:
  """Gets a GoogleAdsClient instance.

  Tries the following in order:
    1. FastMCP OAuth access token (if present)
    2. Environment variables (GOOGLE_ADS_DEVELOPER_TOKEN, etc.)
    3. YAML credentials file (google-ads.yaml)

  Returns:
      A GoogleAdsClient instance.

  Raises:
      ValueError: If no valid credentials are found.
  """
  global _ADS_CLIENT

  access_token = get_access_token()
  if access_token:
    access_token = access_token.token

  if access_token:
    dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not dev_token:
      default_path = f"{ROOT_DIR}/google-ads.yaml"
      cred_path = os.environ.get("GOOGLE_ADS_CREDENTIALS", default_path)
      if os.path.isfile(cred_path):
        with open(cred_path, "r", encoding="utf-8") as f:
          ads_config = yaml.safe_load(f.read())
        dev_token = ads_config.get("developer_token")
    credentials = Credentials(access_token)
    login_cid = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
    login_cid = login_cid.replace("-", "").strip() or None
    return GoogleAdsClient(
        credentials,
        developer_token=dev_token,
        login_customer_id=login_cid,
    )

  if not _ADS_CLIENT:
    env_client = _get_client_from_env()
    if env_client:
      _ADS_CLIENT = env_client
    else:
      default_path = f"{ROOT_DIR}/google-ads.yaml"
      cred_path = os.environ.get("GOOGLE_ADS_CREDENTIALS", default_path)
      if os.path.isfile(cred_path):
        _ADS_CLIENT = GoogleAdsClient.load_from_storage(cred_path)
      else:
        raise ValueError(
            "No Google Ads credentials found. Provide either:\n"
            "  1. Environment variables: GOOGLE_ADS_DEVELOPER_TOKEN, "
            "GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET, "
            "GOOGLE_ADS_REFRESH_TOKEN\n"
            "  2. A google-ads.yaml file (set path via "
            "GOOGLE_ADS_CREDENTIALS env var)"
        )

  return _ADS_CLIENT


@mcp.tool()
def list_accessible_accounts() -> list[str]:
  """Lists Google Ads customers id directly accessible by the user.

  The accounts can be used as `login_customer_id`.
  """
  ads_client = get_ads_client()
  customer_service: CustomerServiceClient = ads_client.get_service(
      "CustomerService"
  )
  accounts = customer_service.list_accessible_customers().resource_names
  return [account.split("/")[-1] for account in accounts]


def preprocess_gaql(query: str) -> str:
  """Preprocesses a GAQL query to add omit_unselected_resource_names=true."""
  if "omit_unselected_resource_names" not in query:
    if "PARAMETERS" in query and "include_drafts" in query:
      return query + " omit_unselected_resource_names=true"
    return query + " PARAMETERS omit_unselected_resource_names=true"
  return query


def format_value(value: Any) -> Any:
  """Formats a value from a Google Ads API response."""
  if isinstance(value, proto.marshal.collections.repeated.Repeated):
    return_value = [format_value(i) for i in value]
  elif isinstance(value, proto.Message):
    # covert to json first to avoid serialization issues
    return_value = proto.Message.to_json(
        value,
        use_integers_for_enums=False,
    )
    return_value = json.loads(return_value)
  elif isinstance(value, proto.Enum):
    return_value = value.name
  else:
    return_value = value

  return return_value


@mcp.tool(
    output_schema={
        "type": "object",
        "properties": {
            "data": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["data"],
    }
)
def execute_gaql(
    query: str,
    customer_id: str,
    login_customer_id: str | None = None,
) -> list[dict[str, Any]]:
  """Executes a Google Ads Query Language (GAQL) query to get reporting data.

  Args:
      query: The GAQL query to execute.
      customer_id: The ID of the customer being queried. It is only digits.
      login_customer_id: (Optional) The ID of the customer being logged in.
          Usually, it is the MCC on top of the target customer account.
          It is only digits.
          In most cases, a default account is set, it could be optional.

  Returns:
      An array of object, each object representing a row of the query results.
  """
  query = preprocess_gaql(query)
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id
  ads_service: GoogleAdsServiceClient = ads_client.get_service(
      "GoogleAdsService"
  )
  try:
    query_res = ads_service.search_stream(query=query, customer_id=customer_id)
    output = []
    for batch in query_res:
      for row in batch.results:
        output.append(
            {
                i: format_value(get_nested_attr(row, i))
                for i in batch.field_mask.paths
            }
        )
  except GoogleAdsException as e:
    raise ToolError("\n".join(str(i) for i in e.failure.errors)) from e

  return {"data": output}


@mcp.tool(
    output_schema={
        "type": "object",
        "properties": {
            "data": {"type": "array", "items": {"type": "object"}},
            "query": {"type": "string"},
        },
        "required": ["data", "query"],
    }
)
def search_ads(
    customer_id: str,
    resource: str,
    fields: list[str],
    conditions: list[str] | None = None,
    orderings: list[str] | None = None,
    limit: int | None = None,
    login_customer_id: str | None = None,
) -> dict[str, Any]:
  """Searches Google Ads data using structured parameters.

  A convenience wrapper around GAQL that builds the query from
  individual components, so you don't need to compose GAQL syntax.

  Use `get_reporting_view_doc` to discover available resources and
  `get_reporting_fields_doc` to discover available fields.

  Args:
      customer_id: The customer account ID (digits only, no dashes).
      resource: The resource to query (e.g. 'campaign', 'ad_group',
          'ad_group_ad', 'keyword_view', 'ad_group_criterion').
      fields: List of fields to select. Each field must be fully
          qualified with the resource prefix
          (e.g. ['campaign.id', 'campaign.name', 'campaign.status',
          'metrics.impressions', 'metrics.clicks']).
      conditions: (Optional) List of WHERE conditions, combined with
          AND (e.g. ["campaign.status = 'ENABLED'",
          "metrics.impressions > 100",
          "segments.date BETWEEN '2025-01-01' AND '2025-01-31'"]).
      orderings: (Optional) List of ORDER BY clauses
          (e.g. ['metrics.impressions DESC']).
      limit: (Optional) Maximum number of rows to return. Required
          for change_event queries (max 10000).
      login_customer_id: (Optional) The MCC account ID if querying
          a sub-account.

  Returns:
      An object with 'data' (array of result rows) and 'query'
      (the generated GAQL for reference).
  """
  query_parts = [f"SELECT {', '.join(fields)} FROM {resource}"]

  if conditions:
    query_parts.append(f" WHERE {' AND '.join(conditions)}")

  if orderings:
    query_parts.append(f" ORDER BY {', '.join(orderings)}")

  if limit is not None:
    query_parts.append(f" LIMIT {limit}")

  query = "".join(query_parts)
  query = preprocess_gaql(query)

  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id
  ads_service: GoogleAdsServiceClient = ads_client.get_service(
      "GoogleAdsService"
  )
  try:
    query_res = ads_service.search_stream(
        query=query, customer_id=customer_id
    )
    output = []
    for batch in query_res:
      for row in batch.results:
        output.append(
            {
                i: format_value(get_nested_attr(row, i))
                for i in batch.field_mask.paths
            }
        )
  except GoogleAdsException as e:
    raise ToolError("\n".join(str(i) for i in e.failure.errors)) from e

  return {"data": output, "query": query}
