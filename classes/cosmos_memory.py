from azure.cosmos import exceptions
from datetime import datetime


class CosmosMemory:
    """
    Long-term user memory using Azure Cosmos DB.
    Stores user preferences, past orders, and settings across sessions.
    """

    def __init__(
        self,
        cosmos_client,
        database_client,
        container_client,
        config,
    ):
        self.cosmos_client = cosmos_client
        self.database_client = database_client
        self.container_client = container_client
        self.ttl_seconds = config["cosmos"]["profile_ttl_seconds"]

    def get_user_or_default_profile(self, user_id):
        user_prefs = self.get_user_profile(user_id)
        if user_prefs is None:
            user_prefs = self._get_default_preferences()
            self.save_user_profile(user_id, user_prefs)
        return user_prefs

    def get_user_profile(self, user_id):
        """Retrieve user preferences from Cosmos DB."""
        # self.debug_container_contents()  # Debugging line to check container contents

        try:
            item = self.container_client.read_item(item=user_id, partition_key=user_id)
            print(f"[LONG-TERM] Loaded profile for user: {user_id}")
            return item["preferences"]
        except exceptions.CosmosResourceNotFoundError:
            print(f"[LONG-TERM] No existing profile found for user: {user_id}")
            return None
        except Exception as error:
            print(f"[LONG-TERM] Error reading profile: {error}")
            return None

    def save_user_profile(self, user_id, preferences):
        """Save or update user preferences in Cosmos DB."""
        profile = {
            "id": user_id,
            "userId": user_id,
            "preferences": preferences,
            "last_updated": datetime.now().isoformat(),
            "ttl": self.ttl_seconds,
        }

        try:
            self.container_client.upsert_item(profile)
            print(f"[LONG-TERM] Saved profile for user: {user_id}")
            return True
        except Exception as error:
            print(f"[LONG-TERM] Error saving profile: {error}")
            return False

    def update_preference(self, user_id, key, value):
        """Update a single preference field."""
        current = self.get_user_profile(user_id) or {}
        current[key] = value
        return self.save_user_profile(user_id, current)

    def _get_default_preferences(self):
        """Return a default preferences dictionary."""
        return {
            "language": "English",
            "language_preference": "professional",
            "email_address": None,
        }

    def debug_container_contents(self):
        """Query all items in container to see what actually exists"""
        print("=== CONTAINER DEBUG ===")

        # 1. Check container partition key definition
        container_props = self.container_client.read()
        print(f"Partition key path: {container_props['partitionKey']['paths']}")

        # 2. Query ALL items (this WILL find your profile if it exists)
        query = "SELECT * FROM c"
        try:
            items = list(
                self.container_client.query_items(
                    query=query,
                    enable_cross_partition_query=True,  # Critical for this to work
                )
            )
            print(f"Total items in container: {len(items)}")
            for item in items:
                print(
                    f"  - id: '{item['id']}', userId: '{item['userId']}', partition key value: '{item['userId']}'"
                )
        except Exception as e:
            print(f"Query failed: {e}")

        # 3. Try to find your specific profile
        profile_id = "luke.ginn"  # Replace with actual user_id
        query2 = "SELECT * FROM c WHERE c.id = @id"
        items2 = list(
            self.container_client.query_items(
                query=query2,
                parameters=[{"name": "@id", "value": profile_id}],
                enable_cross_partition_query=True,
            )
        )
        print(f"Query for id '{profile_id}': {len(items2)} items found")

        return items
