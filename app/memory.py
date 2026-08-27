import json

import redis

from config.settings import settings
from typing import Any, Dict, List, Optional




class ClaimMemory:
    """
    Long-term claim history manager.

    Redis-backed persistent memory with local in-process fallback.

    Stores policyholder claim context such as:
        - Pre-existing diseases
        - Previous claims
        - Policy information
        - Cumulative Sum Insured usage
        - Previous related medical events

    Redis is used when available.
    If Redis is unavailable, the class falls back to local memory.
    """

    def __init__(self):
        # ---------------------------------------------------------
        # Local fallback memory
        # ---------------------------------------------------------
        self._memory: Dict[str, List[Dict[str, Any]]] = {}

        # ---------------------------------------------------------
        # Redis configuration
        # ---------------------------------------------------------
        self.redis_host = settings.redis_host
        self.redis_port = settings.redis_port
        self.redis_password = settings.redis_password
        self.redis_cache_ttl = settings.redis_cache_ttl

        # ---------------------------------------------------------
        # Redis connection
        # ---------------------------------------------------------
        self.redis_client = None
        self.redis_connected = False

        self._connect_redis()

    # =========================================================
    # Redis connection
    # =========================================================

    def _connect_redis(self):
        """
        Connect to Redis.

        Follows the same graceful-fallback approach used by the
        enterprise project.

        If Redis is unavailable, the application continues using
        local in-memory storage.
        """

        try:
            redis_kwargs = {
                "host": self.redis_host,
                "port": self.redis_port,
                "decode_responses": True,
                "socket_timeout": 2,
            }

            # Add username only when configured.

            # Add password only when configured.
            if self.redis_password:
                redis_kwargs["password"] = (
                    self.redis_password
                )

            self.redis_client = redis.Redis(
                **redis_kwargs
            )

            self.redis_client.ping()

            self.redis_connected = True

            print(
                "[REDIS] Connected to Redis successfully."
            )

        except Exception as exc:
            self.redis_client = None
            self.redis_connected = False

            print(
                "[REDIS] Redis server unavailable "
                "({}). Proceeding with local memory.".format(
                    exc
                )
            )

    # =========================================================
    # Redis key
    # =========================================================

    def _redis_key(
        self,
        policyholder_id: str,
    ) -> str:
        """
        Generate deterministic Redis key for a policyholder.
        """

        return (
            "mediclaim:memory:"
            + str(policyholder_id)
        )

    # =========================================================
    # Redis read
    # =========================================================

    def _redis_get_history(
        self,
        policyholder_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve policyholder history from Redis.

        Returns None if Redis is unavailable or the key does
        not exist.
        """

        if not self.redis_connected:
            return None

        try:
            key = self._redis_key(
                policyholder_id
            )

            value = self.redis_client.get(key)

            if not value:
                return []

            data = json.loads(value)

            if isinstance(data, list):
                return data

            return []

        except Exception as exc:
            print(
                "[REDIS] Error reading memory: {}".format(
                    exc
                )
            )

            return None

    # =========================================================
    # Redis write
    # =========================================================

    def _redis_save_history(
        self,
        policyholder_id: str,
        history: List[Dict[str, Any]],
    ) -> bool:
        """
        Persist policyholder history to Redis.
        """

        if not self.redis_connected:
            return False

        try:
            key = self._redis_key(
                policyholder_id
            )

            self.redis_client.setex(
                key,
                self.redis_cache_ttl,
                json.dumps(history),
            )

            return True

        except Exception as exc:
            print(
                "[REDIS] Error writing memory: {}".format(
                    exc
                )
            )

            return False

    # =========================================================
    # Create / initialize policyholder memory
    # =========================================================

    def initialize_policyholder(
        self,
        policyholder_id: str,
    ):
        """
        Create an empty memory record for a policyholder if one
        does not already exist.
        """

        if not policyholder_id:
            raise ValueError(
                "policyholder_id is required"
            )

        # If Redis has the policyholder, nothing else is required.
        if self.redis_connected:
            existing = self._redis_get_history(
                policyholder_id
            )

            if existing:
                return

        # Local fallback.
        if policyholder_id not in self._memory:
            self._memory[policyholder_id] = []

    # =========================================================
    # Add memory
    # =========================================================

    def add_memory(
        self,
        policyholder_id: str,
        memory_type: str,
        data: Dict[str, Any],
    ):
        """
        Add a structured memory item.

        Redis is preferred. Local memory is used as fallback.
        """

        if not policyholder_id:
            raise ValueError(
                "policyholder_id is required"
            )

        if not memory_type:
            raise ValueError(
                "memory_type is required"
            )

        if not isinstance(data, dict):
            raise TypeError(
                "data must be a dictionary"
            )

        record = {
            "type": memory_type,
            "data": dict(data),
        }

        # ---------------------------------------------------------
        # Redis path
        # ---------------------------------------------------------
        if self.redis_connected:

            history = self._redis_get_history(
                policyholder_id
            )

            if history is not None:
                history.append(record)

                if self._redis_save_history(
                    policyholder_id,
                    history,
                ):
                    return

        # ---------------------------------------------------------
        # Local fallback
        # ---------------------------------------------------------
        self.initialize_policyholder(
            policyholder_id
        )

        self._memory[
            policyholder_id
        ].append(record)

    # =========================================================
    # Add claim history
    # =========================================================

    def add_claim(
        self,
        policyholder_id: str,
        claim_id: str,
        claim_data: Dict[str, Any],
    ):
        """
        Store a previous claim in long-term memory.
        """

        if not claim_id:
            raise ValueError(
                "claim_id is required"
            )

        data = dict(claim_data)

        data["claim_id"] = claim_id

        self.add_memory(
            policyholder_id=policyholder_id,
            memory_type="CLAIM",
            data=data,
        )

    # =========================================================
    # Add PED
    # =========================================================

    def add_ped(
        self,
        policyholder_id: str,
        condition: str,
        declared: bool = True,
    ):
        """
        Store a declared or known pre-existing disease.
        """

        if not condition:
            raise ValueError(
                "condition is required"
            )

        self.add_memory(
            policyholder_id=policyholder_id,
            memory_type="PED",
            data={
                "condition": condition,
                "declared": declared,
            },
        )

    # =========================================================
    # Add policy information
    # =========================================================

    def add_policy(
        self,
        policyholder_id: str,
        policy_id: str,
        sum_insured: float,
        remaining_sum_insured: float,
    ):
        """
        Store policy financial information.
        """

        if sum_insured < 0:
            raise ValueError(
                "sum_insured cannot be negative"
            )

        if remaining_sum_insured < 0:
            raise ValueError(
                "remaining_sum_insured cannot be negative"
            )

        if remaining_sum_insured > sum_insured:
            raise ValueError(
                "remaining_sum_insured cannot exceed "
                "sum_insured"
            )

        self.add_memory(
            policyholder_id=policyholder_id,
            memory_type="POLICY",
            data={
                "policy_id": policy_id,
                "sum_insured": sum_insured,
                "remaining_sum_insured": (
                    remaining_sum_insured
                ),
            },
        )

    # =========================================================
    # Retrieve all memory
    # =========================================================

    def get_history(
        self,
        policyholder_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Return all stored memories for a policyholder.

        Redis is preferred. Local memory is the fallback.
        """

        if self.redis_connected:
            history = self._redis_get_history(
                policyholder_id
            )

            if history is not None:
                return list(history)

        return list(
            self._memory.get(
                policyholder_id,
                [],
            )
        )

    # =========================================================
    # Retrieve by memory type
    # =========================================================

    def get_by_type(
        self,
        policyholder_id: str,
        memory_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories of a specific type.
        """

        history = self.get_history(
            policyholder_id
        )

        return [
            item
            for item in history
            if item.get("type") == memory_type
        ]

    # =========================================================
    # Get PEDs
    # =========================================================

    def get_peds(
        self,
        policyholder_id: str,
    ) -> List[Dict[str, Any]]:
        return self.get_by_type(
            policyholder_id,
            "PED",
        )

    # =========================================================
    # Get previous claims
    # =========================================================

    def get_claims(
        self,
        policyholder_id: str,
    ) -> List[Dict[str, Any]]:
        return self.get_by_type(
            policyholder_id,
            "CLAIM",
        )

    # =========================================================
    # Get policy information
    # =========================================================

    def get_policies(
        self,
        policyholder_id: str,
    ) -> List[Dict[str, Any]]:
        return self.get_by_type(
            policyholder_id,
            "POLICY",
        )

    # =========================================================
    # Get remaining Sum Insured
    # =========================================================

    def get_remaining_sum_insured(
        self,
        policyholder_id: str,
        policy_id: Optional[str] = None,
    ) -> Optional[float]:
        """
        Return the latest remaining Sum Insured.

        If policy_id is provided, only matching policy records
        are considered.
        """

        policies = self.get_policies(
            policyholder_id
        )

        if policy_id:
            policies = [
                policy
                for policy in policies
                if policy.get(
                    "data",
                    {},
                ).get(
                    "policy_id"
                ) == policy_id
            ]

        if not policies:
            return None

        latest = policies[-1]

        return latest.get(
            "data",
            {},
        ).get(
            "remaining_sum_insured"
        )

    # =========================================================
    # Update remaining Sum Insured
    # =========================================================

    def update_remaining_sum_insured(
        self,
        policyholder_id: str,
        policy_id: str,
        remaining_sum_insured: float,
    ):
        """
        Add a new policy state with updated Remaining Sum Insured.
        """

        if remaining_sum_insured < 0:
            raise ValueError(
                "remaining_sum_insured cannot be negative"
            )

        policies = self.get_policies(
            policyholder_id
        )

        matching = [
            item
            for item in policies
            if item.get(
                "data",
                {},
            ).get(
                "policy_id"
            ) == policy_id
        ]

        if not matching:
            raise ValueError(
                "Policy not found in memory: {}".format(
                    policy_id
                )
            )

        latest_policy = matching[-1]

        original_sum_insured = (
            latest_policy[
                "data"
            ].get(
                "sum_insured",
                0.0,
            )
        )

        if remaining_sum_insured > original_sum_insured:
            raise ValueError(
                "Remaining Sum Insured cannot exceed "
                "original Sum Insured"
            )

        self.add_policy(
            policyholder_id=policyholder_id,
            policy_id=policy_id,
            sum_insured=original_sum_insured,
            remaining_sum_insured=(
                remaining_sum_insured
            ),
        )

    # =========================================================
    # Search memory
    # =========================================================

    def search(
        self,
        policyholder_id: str,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Simple deterministic memory search.

        This preserves the existing implementation and works
        against Redis-backed history.
        """

        if not query:
            return []

        query_terms = set(
            query.lower().split()
        )

        results = []

        for item in self.get_history(
            policyholder_id
        ):
            item_text = str(
                item
            ).lower()

            matches = sum(
                1
                for term in query_terms
                if term in item_text
            )

            if matches > 0:
                results.append(
                    {
                        "memory": item,
                        "score": matches,
                    }
                )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return results

    # =========================================================
    # Clear policyholder memory
    # =========================================================

    def clear(
        self,
        policyholder_id: str,
    ):
        """
        Delete all memory for a policyholder.
        """

        if self.redis_connected:
            try:
                self.redis_client.delete(
                    self._redis_key(
                        policyholder_id
                    )
                )
            except Exception as exc:
                print(
                    "[REDIS] Error clearing memory: {}".format(
                        exc
                    )
                )

        self._memory.pop(
            policyholder_id,
            None,
        )

    # =========================================================
    # Count memories
    # =========================================================

    def count(
        self,
        policyholder_id: str,
    ) -> int:
        return len(
            self.get_history(
                policyholder_id
            )
        )

    # =========================================================
    # Memory backend status
    # =========================================================

    def get_backend_status(self) -> Dict[str, Any]:
        """
        Return memory backend status for demo/UI/debugging.
        """

        return {
            "backend": (
                "redis"
                if self.redis_connected
                else "local"
            ),
            "redis_connected": (
                self.redis_connected
            ),
            "redis_host": self.redis_host,
            "redis_port": self.redis_port,
        }


# =============================================================
# Global memory instance
# =============================================================

memory = ClaimMemory()