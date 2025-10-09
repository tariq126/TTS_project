import json
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from workers.hooks import on_job_completed

class TestHooks(unittest.TestCase):

    @patch('workers.hooks.redis_client')
    @patch('workers.hooks.graphql_client')
    def test_on_job_completed(self, mock_graphql_client, mock_redis_client):
        # Arrange
        job_id = 'test_job_id'
        final_urls = {'primary_url': 'http://example.com/audio.mp3'}
        project_id = 'test_project_id'

        mock_redis_client.hgetall.return_value = {
            b'project_id': project_id.encode('utf-8'),
            b'blocks': json.dumps([{'text': 'block 1'}]).encode('utf-8')
        }

        # Act
        on_job_completed(job_id, final_urls)

        # Assert
        mock_graphql_client.insert_blocks.assert_called_once()
        call_args = mock_graphql_client.insert_blocks.call_args[1]

        self.assertEqual(call_args['project_id'], project_id)
        self.assertEqual(call_args['content'], 'final_audio')
        self.assertEqual(call_args['s3_url'], 'http://example.com/audio.mp3')
        self.assertEqual(call_args['block_index'], -1)
        self.assertIn('created_at', call_args)

if __name__ == '__main__':
    unittest.main()
