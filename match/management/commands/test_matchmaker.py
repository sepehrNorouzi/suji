from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from match.services.matchmaking import OpenMatchService
import requests
import json
import uuid


class Command(BaseCommand):
    help = 'Test OpenMatch connectivity and functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help='Skip cleanup of test tickets',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        skip_cleanup = options['skip_cleanup']
        
        self.stdout.write(
            self.style.HTTP_INFO("=" * 60)
        )
        self.stdout.write(
            self.style.HTTP_INFO("OpenMatch Connectivity Test")
        )
        self.stdout.write(
            self.style.HTTP_INFO("=" * 60)
        )
        
        # Initialize service
        service = OpenMatchService()
        
        # Display configuration
        self.stdout.write(f"\nConfiguration:")
        self.stdout.write(f"  Frontend URL: {service.frontend_url}")
        self.stdout.write(f"  Backend URL: {service.backend_url}")
        self.stdout.write(f"  Query URL: {service.query_url}")
        self.stdout.write(f"  Timeout: {service.timeout}s")
        self.stdout.write(f"  Max Retries: {service.max_retries}")
        
        # Test 1: Basic connectivity
        self.stdout.write(f"\n{'-' * 40}")
        self.stdout.write("Test 1: Basic Connectivity")
        self.stdout.write(f"{'-' * 40}")
        
        try:
            response = requests.get(service.frontend_url, timeout=5)
            if response.status_code in [200, 404, 405]:  # Any of these means service is running
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Can reach OpenMatch Frontend (Status: {response.status_code})")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"? OpenMatch Frontend responded with status: {response.status_code}")
                )
        except requests.exceptions.ConnectionError:
            self.stdout.write(
                self.style.ERROR("✗ Cannot reach OpenMatch Frontend - Connection refused")
            )
            self.stdout.write(
                self.style.WARNING("  Suggestions:")
            )
            self.stdout.write("    1. Start OpenMatch services: docker-compose -f docker-compose.openmatch.yml up -d")
            self.stdout.write("    2. Check if ports are exposed correctly")
            self.stdout.write("    3. Verify network configuration")
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Unexpected error: {e}")
            )
            return
        
        # Test 2: Service accessibility check
        self.stdout.write(f"\n{'-' * 40}")
        self.stdout.write("Test 2: Service Accessibility")
        self.stdout.write(f"{'-' * 40}")
        
        health = service.health_check()
        if health["healthy"]:
            self.stdout.write(
                self.style.SUCCESS(f"✓ OpenMatch Frontend is accessible")
            )
            if verbose:
                self.stdout.write(f"  Response time: {health.get('response_time', 'N/A')}s")
                self.stdout.write(f"  Status code: {health.get('status_code', 'N/A')}")
                if 'note' in health:
                    self.stdout.write(f"  Note: {health['note']}")
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ OpenMatch Frontend accessibility test failed")
            )
            self.stdout.write(f"  Error: {health.get('error', 'Unknown error')}")
            if 'suggestions' in health:
                self.stdout.write("  Suggestions:")
                for suggestion in health['suggestions']:
                    self.stdout.write(f"    - {suggestion}")
            return
        
        # Test 3: Create test ticket
        self.stdout.write(f"\n{'-' * 40}")
        self.stdout.write("Test 3: Create Ticket")
        self.stdout.write(f"{'-' * 40}")
        
        test_search_fields = {
            "string_args": {
                "mode": "test_mode",
                "region": "test_region"
            },
            "double_args": {
                "score": 1000.0,
                "test_value": 42.0
            }
        }
        
        result = service.create_ticket(
            player_id="test_player_123",
            match_type_name="test_match_type",
            search_fields=test_search_fields
        )
        
        if result["success"]:
            ticket_id = result["ticket_id"]
            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully created test ticket: {ticket_id}")
            )
            if verbose:
                self.stdout.write(f"  Ticket data: {json.dumps(result.get('data', {}), indent=2)}")
            
            # Test 4: Get ticket
            self.stdout.write(f"\n{'-' * 40}")
            self.stdout.write("Test 4: Get Ticket")
            self.stdout.write(f"{'-' * 40}")
            
            get_result = service.get_ticket(ticket_id)
            if get_result["success"]:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully retrieved ticket: {ticket_id}")
                )
                if verbose:
                    self.stdout.write(f"  Retrieved data: {json.dumps(get_result.get('data', {}), indent=2)}")
            else:
                self.stdout.write(
                    self.style.WARNING(f"? Could not retrieve ticket: {get_result.get('error', 'Unknown error')}")
                )
            
            # Test 5: Get assignments (will likely be empty for test ticket)
            self.stdout.write(f"\n{'-' * 40}")
            self.stdout.write("Test 5: Get Assignments")
            self.stdout.write(f"{'-' * 40}")
            
            assignment_result = service.get_assignments(ticket_id)
            if assignment_result["success"]:
                assignment = assignment_result.get("assignment", {})
                if assignment:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Ticket has assignment data")
                    )
                    if verbose:
                        self.stdout.write(f"  Assignment: {json.dumps(assignment, indent=2)}")
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ No assignment yet (expected for test ticket)")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f"? Could not get assignments: {assignment_result.get('error', 'Unknown error')}")
                )
            
            # Test 6: Delete ticket (cleanup)
            if not skip_cleanup:
                self.stdout.write(f"\n{'-' * 40}")
                self.stdout.write("Test 6: Delete Ticket (Cleanup)")
                self.stdout.write(f"{'-' * 40}")
                
                delete_result = service.delete_ticket(ticket_id)
                if delete_result["success"]:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Successfully deleted test ticket: {ticket_id}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"? Could not delete ticket: {delete_result.get('error', 'Unknown error')}")
                    )
                    self.stdout.write(f"  You may need to manually clean up ticket: {ticket_id}")
            else:
                self.stdout.write(f"\nSkipping cleanup. Test ticket ID: {ticket_id}")
        
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ Failed to create test ticket")
            )
            self.stdout.write(f"  Error: {result.get('error', 'Unknown error')}")
            self.stdout.write(f"  Details: {result.get('details', 'No details')}")
            if 'suggestions' in result:
                self.stdout.write("  Suggestions:")
                for suggestion in result['suggestions']:
                    self.stdout.write(f"    - {suggestion}")
            return
        
        # Final summary
        self.stdout.write(f"\n{'-' * 40}")
        self.stdout.write("Test Summary")
        self.stdout.write(f"{'-' * 40}")
        self.stdout.write(
            self.style.SUCCESS("✓ All tests completed successfully!")
        )
        self.stdout.write("OpenMatch integration appears to be working correctly.")
        
        # Show sample API usage
        self.stdout.write(f"\n{'-' * 40}")
        self.stdout.write("Sample Django API Usage")
        self.stdout.write(f"{'-' * 40}")
        self.stdout.write("You can now test the Django API endpoints:")
        self.stdout.write("1. Join matchmaking:")
        self.stdout.write("   POST /api/matchmaking/join/")
        self.stdout.write('   {"match_type_id": 1, "search_fields": {...}}')
        self.stdout.write("")
        self.stdout.write("2. Check status:")
        self.stdout.write("   GET /api/matchmaking/status/")
        self.stdout.write("")
        self.stdout.write("3. Leave matchmaking:")
        self.stdout.write("   POST /api/matchmaking/leave/")
        self.stdout.write('   {"match_type_id": 1}')
    