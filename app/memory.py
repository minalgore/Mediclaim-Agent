from typing import Any, Dict, List, Optional


class ClaimMemory:
    """
    Long-term claim history manager.

    Stores policyholder claim context such as:

        - Pre-existing diseases
        - Previous claims
        - Policy information
        - Cumulative Sum Insured usage
        - Previous related medical events

    The class exposes a Mem0-compatible abstraction so that
    the rest of the application does not depend directly on
    a particular Mem0 implementation.
    """

    def __init__(self):
        self._memory: Dict[str, List[Dict[str, Any]]] = {}

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

        Example:

            memory.add_memory(
                "POLICYHOLDER-001",
                "PED",
                {
                    "condition": "Diabetes",
                    "status": "declared"
                }
            )
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

        self.initialize_policyholder(
            policyholder_id
        )

        record = {
            "type": memory_type,
            "data": dict(data),
        }

        self._memory[policyholder_id].append(
            record
        )

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
                "remaining_sum_insured cannot exceed sum_insured"
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
        """

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
                if policy.get("data", {}).get(
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
        Add a new policy state with updated remaining Sum Insured.
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
            if item.get("data", {}).get(
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

        original_sum_insured = latest_policy[
            "data"
        ].get(
            "sum_insured",
            0.0,
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
        Simple local memory search.

        This is intentionally deterministic for development.

        The production Mem0 implementation can replace this
        method with semantic memory search.
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
        Delete all local memory for a policyholder.
        """

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
            self._memory.get(
                policyholder_id,
                [],
            )
        )