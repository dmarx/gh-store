# gh_store/core/uid.py

from dataclasses import dataclass

@dataclass
class UIDConfig:
    """Configuration for UID handling"""
    prefix: str  # e.g. "UID:"
    base_label: str  # e.g. "stored-object"

class UIDUtils:
    """Utilities for handling UIDs throughout the application"""
    
    def __init__(self, config: UIDConfig):
        self.config = config

    def add_prefix(self, object_id: str) -> str:
        """Add UID prefix to object ID if not present"""
        if object_id.startswith(self.config.prefix):
            return object_id
        return f"{self.config.prefix}{object_id}"

    def remove_prefix(self, label: str) -> str:
        """Remove UID prefix from label if present"""
        if label.startswith(self.config.prefix):
            return label[len(self.config.prefix):]
        return label

    def get_id_from_labels(self, labels) -> str | None:
        """Extract object ID from a list of labels, stripping prefix"""
        for label in labels:
            # Handle both string and github.Label.Label objects
            label_name = getattr(label, 'name', label)
            
            if (label_name != self.config.base_label and 
                isinstance(label_name, str)):
                return self.remove_prefix(label_name)
        return None

    def format_for_query(self, object_id: str) -> list[str]:
        """Format object ID for GitHub API queries"""
        return [self.config.base_label, self.add_prefix(object_id)]

    def is_uid_label(self, label: str) -> bool:
        """Check if a label is a UID label"""
        return label.startswith(self.config.prefix)

    def validate_object_meta(self, object_id: str, label: str) -> bool:
        """
        Validate that an object's ID and label are consistent
        
        Args:
            object_id: The raw object ID
            label: The label associated with the object
            
        Returns:
            bool: True if the ID and label are consistent
        """
        expected_label = self.add_prefix(object_id)
        return label == expected_label
