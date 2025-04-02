import requests
from log import Log
from repository.repository import Repository, RepositoryError
import re


class GitHub(Repository):

    def __init__(self, token: str, repo_owner: str, repo_name: str, pull_number: str = None):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.pull_number = pull_number
        self.__header_accept_json = {"Authorization": f"token {token}",
                                      "Accept": "application/vnd.github+json"}
        self.__header_authorization = {"Accept": "application/vnd.github.v3+json"}
        self.__url_add_comment = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pull_number}/comments"
        self.__url_add_issue = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pull_number}/comments"

    def update_comment(self, comment_id: str, new_body: str):
        """Cập nhật một comment trên PR bằng API GitHub."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues/comments/{comment_id}"
        headers = self.__header_accept_json | self.__header_authorization
        body = {"body": new_body}

        response = requests.patch(url, json=body, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise RepositoryError(f"Error updating comment {response.status_code}: {response.text}")

    def get_comments(self):
        """Lấy tất cả các comment trên PR."""
        headers = self.__header_accept_json | self.__header_authorization
        response = requests.get(self.__url_add_issue, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise RepositoryError(f"Error fetching comments {response.status_code}: {response.text}")

    def post_comment_general(self, text):
        headers = self.__header_accept_json | self.__header_authorization
        body = {"body": text}

        response = requests.post(self.__url_add_issue, json=body, headers=headers)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise RepositoryError(f"Error with general comment {response.status_code} : {response.text}")

    def get_latest_commit_id(self) -> str:
        # Lấy danh sách tất cả các PR mở
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls?state=open"
        headers = self.__header_accept_json | self.__header_authorization

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            pull_requests = response.json()
            if not pull_requests:
                raise RepositoryError("No open pull requests found.")

            # Tìm PR có nhánh head trùng với pull request đang làm việc
            matching_pr = next(
                (pr for pr in pull_requests if pr["number"] == int(self.pull_number)),
                None
            )

            if not matching_pr:
                raise RepositoryError(f"No matching open PR found for branch {self.pull_number}.")

            print(f"Pull requests fetched: {[pr['number'] for pr in pull_requests]}")
            print(f"Checking for PR number: {self.pull_number} (type: {type(self.pull_number)})")

            commits_url = matching_pr["commits_url"]
            commits_response = requests.get(commits_url, headers=headers)
            if commits_response.status_code == 200:
                commits = commits_response.json()
                if commits:
                    return commits[-1]["sha"]
                else:
                    raise RepositoryError("No commits found in this pull request.")
            else:
                raise RepositoryError(
                    f"Error fetching commits {commits_response.status_code}: {commits_response.text}")

        else:
            raise RepositoryError(f"Error fetching pull requests {response.status_code}: {response.text}")

    def get_pull_request(self):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{self.pull_number}"
        headers = self.__header_accept_json | self.__header_authorization
        response = requests.get(url, headers=headers)
        return response.json()

    def update_pull_request(self, new_body):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{self.pull_number}"
        headers = self.__header_accept_json | self.__header_authorization
        data = {"body": new_body}
        response = requests.patch(url, json=data, headers=headers)
        return response.json()

    def _get_pull_request_diff(self):
        """Lấy diff của pull request từ GitHub API."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{self.pull_number}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3.diff"
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.text
        else:
            raise RepositoryError(f"Error getting diff: {response.status_code}")

    def _extract_diff_hunk_for_line(self, file_path, line_number, context_lines=3):
        """Trích xuất diff hunk chứa dòng cụ thể, với context."""

        diff_text = self._get_pull_request_diff()
        if not diff_text:
            return None

        hunk_start_pattern = re.compile(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")
        lines = diff_text.splitlines()
        current_hunk = None
        hunk_lines = []
        hunk_start_index = None

        for i, line in enumerate(lines):
            if line.startswith("diff --git") and file_path not in line:
                continue
            elif line.startswith("@@"):
                match = hunk_start_pattern.match(line)
                if match:
                    old_start, old_length, new_start, new_length = match.groups()

                    try:
                        new_start = int(new_start)
                        new_length = int(new_length) if new_length else 1
                    except ValueError:
                        print(f"Invalid number format in diff hunk: {line}")
                        return None

                    if new_start <= line_number <= new_start + new_length - 1:
                        current_hunk = {
                            "start": new_start,
                            "lines": []
                        }
                        hunk_start_index = i
                    else:
                        current_hunk = None
                    hunk_lines = []

            elif current_hunk is not None:
                hunk_lines.append(line)

        if current_hunk and hunk_start_index is not None:
            start_index = max(0, hunk_start_index - context_lines)
            end_index = min(len(lines), hunk_start_index + len(hunk_lines) + context_lines)
            context_hunk_lines = lines[start_index:end_index]
            return "\n".join(context_hunk_lines)

        return None

    def _get_diff_hunk_for_line(self, file_path, line_number):
      """
      Lấy diff hunk cho một dòng cụ thể.

      Args:
          file_path: Đường dẫn tới file.
          line_number: Số dòng.

      Returns:
          str: Diff hunk nếu tìm thấy, None nếu không.
      """
      try:
          return self._extract_diff_hunk_for_line(file_path, line_number)
      except RepositoryError as e:
          print(f"Lỗi khi lấy diff hunk: {e}")
          return None