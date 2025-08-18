# match/services/openmatch_service.py (corrected version)
import json
import uuid
import logging
import requests
import time
from typing import Dict, Optional, List
from django.conf import settings
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class OpenMatchService:
    """
    Service class for interacting with OpenMatch Frontend API
    OpenMatch 1.8.1 doesn't have health endpoints, so we'll use the actual API endpoints
    """
    
    def __init__(self):
        # Get OpenMatch configuration from Django settings
        self.frontend_url = getattr(settings, 'OPENMATCH_FRONTEND_URL', 'http://localhost:51504')
        self.backend_url = getattr(settings, 'OPENMATCH_BACKEND_URL', 'http://localhost:51505')
        self.query_url = getattr(settings, 'OPENMATCH_QUERY_URL', 'http://localhost:51503')
        self.timeout = getattr(settings, 'OPENMATCH_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'OPENMATCH_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'OPENMATCH_RETRY_DELAY', 1)
    
    def _make_request_with_retries(self, method: str, url: str, **kwargs) -> Dict:
        """
        Make HTTP request with retries and comprehensive error handling
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Attempting request {attempt + 1}/{self.max_retries} to {url}")
                
                response = requests.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                
                logger.debug(f"Request successful: {response.status_code}")
                return {"success": True, "response": response}
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (attempt + 1)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.error(f"Request timeout after {self.timeout}s: {str(e)}")
                break  # Don't retry timeouts
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error(f"Request exception: {str(e)}")
                break  # Don't retry other request exceptions
        
        # All retries failed, return error details
        error_type = type(last_exception).__name__
        
        if isinstance(last_exception, requests.exceptions.ConnectionError):
            return {
                "success": False,
                "error": "Connection failed",
                "error_type": error_type,
                "details": f"Cannot connect to {url}. Please check if OpenMatch is running and accessible.",
                "suggestions": [
                    "Verify OpenMatch services are running: docker-compose -f docker-compose.openmatch.yml ps",
                    f"Test connectivity: curl -v {url}",
                    "Check network configuration and firewall settings",
                    "Ensure correct URL in environment variables"
                ],
                "original_error": str(last_exception)
            }
        elif isinstance(last_exception, requests.exceptions.Timeout):
            return {
                "success": False,
                "error": "Request timeout",
                "error_type": error_type,
                "details": f"Request to {url} timed out after {self.timeout} seconds",
                "suggestions": [
                    f"Increase OPENMATCH_TIMEOUT (currently {self.timeout}s)",
                    "Check OpenMatch service performance",
                    "Verify network latency to OpenMatch"
                ],
                "original_error": str(last_exception)
            }
        else:
            return {
                "success": False,
                "error": "Request failed",
                "error_type": error_type,
                "details": str(last_exception),
                "original_error": str(last_exception)
            }
    
    def health_check(self) -> Dict:
        """
        Check if OpenMatch Frontend service is accessible
        """
        test_url = self.frontend_url
        
        logger.info(f"Testing OpenMatch Frontend accessibility at {test_url}")
        result = self._make_request_with_retries("GET", test_url)
        
        if result["success"]:
            response = result["response"]
            # Any response (even 404) means the service is running
            if response.status_code in [200, 404, 405]:  # 405 = Method Not Allowed is also OK
                logger.info("OpenMatch Frontend is accessible")
                return {
                    "healthy": True,
                    "url": test_url,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "note": "Service is accessible (no health endpoint in OpenMatch 1.8.1)"
                }
            else:
                logger.warning(f"OpenMatch Frontend returned unexpected status {response.status_code}")
                return {
                    "healthy": False,
                    "url": test_url,
                    "status_code": response.status_code,
                    "error": f"Unexpected status code: {response.status_code}",
                    "response_text": response.text[:500]
                }
        else:
            logger.error(f"OpenMatch Frontend accessibility test failed: {result['error']}")
            return {
                "healthy": False,
                "url": test_url,
                "error": result["error"],
                "details": result.get("details", ""),
                "suggestions": result.get("suggestions", [])
            }
    
    def create_ticket(self, player_id: str, match_type_name: str, search_fields: Dict) -> Dict:
        """
        Create a matchmaking ticket in OpenMatch
        """
        try:
            ticket_id = f"ticket_{player_id}_{uuid.uuid4().hex[:8]}"
            
            ticket_data = {
                "ticket": {
                    "id": ticket_id,
                    "search_fields": {
                        "tags": [match_type_name],
                        "double_args": search_fields.get("double_args", {}),
                        "string_args": {
                            "mode": match_type_name,
                            "player_id": str(player_id),
                            **search_fields.get("string_args", {})
                        }
                    }
                }
            }
            
            url = f"{self.frontend_url}/v1/frontendservice/tickets"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            logger.info(f"Creating OpenMatch ticket: {ticket_id} for player {player_id}")
            logger.debug(f"Ticket data: {json.dumps(ticket_data, indent=2)}")
            
            result = self._make_request_with_retries(
                "POST",
                url,
                json=ticket_data,
                headers=headers
            )
            
            if result["success"]:
                response = result["response"]
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        logger.info(f"Successfully created ticket: {ticket_id}")
                        return {
                            "success": True,
                            "ticket_id": ticket_id,
                            "data": response_data
                        }
                    except json.JSONDecodeError:
                        # Sometimes OpenMatch returns empty response on success
                        logger.info(f"Successfully created ticket: {ticket_id} (empty response)")
                        return {
                            "success": True,
                            "ticket_id": ticket_id,
                            "data": {"ticket": {"id": ticket_id}}
                        }
                else:
                    logger.error(f"Failed to create ticket: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"OpenMatch API error: {response.status_code}",
                        "details": response.text[:1000],
                        "status_code": response.status_code
                    }
            else:
                logger.error(f"Network error creating ticket: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "details": result.get("details", ""),
                    "suggestions": result.get("suggestions", [])
                }
                
        except Exception as e:
            logger.error(f"Unexpected error creating ticket: {str(e)}")
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }
    
    def delete_ticket(self, ticket_id: str) -> Dict:
        """
        Delete a matchmaking ticket from OpenMatch
        """
        try:
            # OpenMatch Frontend API endpoint for deleting tickets
            url = f"{self.frontend_url}/v1/frontendservice/tickets/{ticket_id}"
            headers = {
                'Accept': 'application/json'
            }
            
            logger.info(f"Deleting OpenMatch ticket: {ticket_id}")
            result = self._make_request_with_retries(
                "DELETE",
                url,
                headers=headers
            )
            
            if result["success"]:
                response = result["response"]
                # OpenMatch DELETE typically returns 200 for success, 404 if not found
                if response.status_code in [200, 204, 404]:
                    logger.info(f"Successfully deleted ticket: {ticket_id}")
                    return {
                        "success": True,
                        "ticket_id": ticket_id,
                        "status_code": response.status_code
                    }
                else:
                    logger.error(f"Failed to delete ticket: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"OpenMatch API error: {response.status_code}",
                        "details": response.text[:1000],
                        "status_code": response.status_code
                    }
            else:
                logger.error(f"Network error deleting ticket: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "details": result.get("details", ""),
                    "suggestions": result.get("suggestions", [])
                }
                
        except Exception as e:
            logger.error(f"Unexpected error deleting ticket: {str(e)}")
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }
    
    def get_ticket(self, ticket_id: str) -> Dict:
        """
        Get ticket information from OpenMatch
        """
        try:
            url = f"{self.frontend_url}/v1/frontendservice/tickets/{ticket_id}"
            headers = {
                'Accept': 'application/json'
            }
            
            logger.debug(f"Getting OpenMatch ticket: {ticket_id}")
            result = self._make_request_with_retries(
                "GET",
                url,
                headers=headers
            )
            
            if result["success"]:
                response = result["response"]
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        return {
                            "success": True,
                            "ticket_id": ticket_id,
                            "data": response_data
                        }
                    except json.JSONDecodeError:
                        return {
                            "success": False,
                            "error": "Invalid JSON response from OpenMatch",
                            "details": response.text[:500]
                        }
                else:
                    return {
                        "success": False,
                        "error": f"OpenMatch API error: {response.status_code}",
                        "details": response.text[:1000],
                        "status_code": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "error": result["error"],
                    "details": result.get("details", ""),
                    "suggestions": result.get("suggestions", [])
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }
    
    def get_assignments(self, ticket_id: str) -> Dict:
        """
        Get ticket assignments from OpenMatch
        """
        try:
            url = f"{self.frontend_url}/v1/frontendservice/tickets/{ticket_id}/assignments"
            headers = {
                'Accept': 'application/json'
            }
            
            result = self._make_request_with_retries(
                "GET",
                url,
                headers=headers
            )
            
            if result["success"]:
                response = result["response"]
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        return {
                            "success": True,
                            "ticket_id": ticket_id,
                            "assignment": response_data.get("assignment", {})
                        }
                    except json.JSONDecodeError:
                        return {
                            "success": False,
                            "error": "Invalid JSON response from OpenMatch",
                            "details": response.text[:500]
                        }
                else:
                    return {
                        "success": False,
                        "error": f"OpenMatch API error: {response.status_code}",
                        "details": response.text[:1000],
                        "status_code": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "error": result["error"],
                    "details": result.get("details", ""),
                    "suggestions": result.get("suggestions", [])
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }
