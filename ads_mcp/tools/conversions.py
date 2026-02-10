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

"""Offline conversion tools for the Google Ads API."""

from typing import Any

from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

from ads_mcp.coordinator import mcp_server as mcp
from ads_mcp.tools.api import get_ads_client


@mcp.tool()
def upload_offline_conversion(
    customer_id: str,
    conversion_action_id: str,
    gclid: str,
    conversion_date_time: str,
    conversion_value: float | None = None,
    currency_code: str | None = None,
    login_customer_id: str | None = None,
) -> dict[str, str | float]:
  """Uploads an offline click conversion.

  Args:
      customer_id: The customer ID containing only digits.
      conversion_action_id: The conversion action ID containing only digits.
      gclid: Google click identifier.
      conversion_date_time: Timestamp in yyyy-mm-dd hh:mm:ss+|-hh:mm format.
      conversion_value: Optional conversion value.
      currency_code: Optional ISO 4217 currency code.
      login_customer_id: Optional manager account ID containing only digits.

  Returns:
      Uploaded conversion metadata.
  """
  ads_client = get_ads_client()
  if login_customer_id:
    ads_client.login_customer_id = login_customer_id

  conversion_upload_service: Any = ads_client.get_service(
      "ConversionUploadService"
  )
  conversion_action_service: Any = ads_client.get_service(
      "ConversionActionService"
  )

  try:
    click_conversion: Any = ads_client.get_type("ClickConversion")
    click_conversion.conversion_action = (
        conversion_action_service.conversion_action_path(
            customer_id,
            conversion_action_id,
        )
    )
    click_conversion.gclid = gclid
    click_conversion.conversion_date_time = conversion_date_time

    if conversion_value is not None:
      click_conversion.conversion_value = conversion_value
    if currency_code is not None:
      click_conversion.currency_code = currency_code

    request: Any = ads_client.get_type("UploadClickConversionsRequest")
    request.customer_id = customer_id
    request.conversions.append(click_conversion)
    request.partial_failure = True

    response = conversion_upload_service.upload_click_conversions(
        request=request
    )
    result = response.results[0]
    return {
        "conversion_action": result.conversion_action,
        "conversion_date_time": result.conversion_date_time,
        "gclid": result.gclid,
    }
  except GoogleAdsException as exc:
    raise ToolError(
        "\n".join(str(error) for error in exc.failure.errors)
    ) from exc
